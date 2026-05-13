#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import math
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path


MSG_QUERY_REQUEST = 1
MSG_QUERY_RESPONSE = 2
MSG_COMMAND_REQUEST = 3
MSG_COMMAND_RESPONSE = 4
MSG_IMU_RESPONSE = 5

QUERY_REALTIME_STATUS = 1

CMD_SET_MOTION_MODEL = 2
CMD_PERFORM_ACTION = 3
CMD_RESET = 4
CMD_ULTRASONIC_OBSTACLE = 5
CMD_EMERGENCY_STOP = 6
CMD_CAMERA_STREAM = 9
CMD_STAND_UP = 10
CMD_LIE_DOWN = 11
CMD_ENABLE_IMU = 20
CMD_DISABLE_IMU = 21

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MODE_LYING_DOWN_WITHOUT_RESET = 0
MODE_LYING_DOWN = 1
MODE_STANDING = 2
MODE_LOW_POSTURE = 3
MODE_FALLEN = 4


def clamp(value, low=-1.0, high=1.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(low, min(high, number))


class RealSenseStreamer:
    DEFAULT_POINTCLOUD_MAX_POINTS = 20000

    def __init__(
        self,
        gateway,
        width=640,
        height=480,
        fps=24,
        jpeg_quality=45,
        publish_fps=24,
        enable_pointcloud=True,
        pointcloud_fps=10,
        pointcloud_max_points=DEFAULT_POINTCLOUD_MAX_POINTS,
    ):
        self.gateway = gateway
        self.width = width
        self.height = height
        self.fps = fps
        self.jpeg_quality = jpeg_quality
        self.publish_interval = 1.0 / max(1, publish_fps)
        self.pointcloud_supported = enable_pointcloud
        self.pointcloud_active = threading.Event()
        self.pointcloud_interval = 1.0 / max(1, pointcloud_fps)
        self.pointcloud_max_points = max(1000, pointcloud_max_points)
        self.running = threading.Event()
        self.thread = None
        self.pipeline = None
        self.align = None
        self.pointcloud = None
        self.last_error = None
        self.last_frame_time = 0
        self.last_pointcloud_time = 0

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running.set()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running.clear()
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

    def loop(self):
        try:
            import cv2
            import numpy as np
            import pyrealsense2 as rs
        except Exception as exc:
            self.report_status(False, f"RealSense dependencies unavailable: {exc}")
            return

        while self.running.is_set() and self.gateway.running.is_set():
            try:
                pipeline, active_fps = self.start_pipeline(rs)
                self.pipeline = pipeline
                self.align = rs.align(rs.stream.color)
                self.pointcloud = rs.pointcloud()
                self.last_error = None
                self.report_status(True, f"RealSense RGB/depth stream started ({active_fps} FPS capture)")
                self.capture_loop(cv2, np, pipeline)
            except Exception as exc:
                self.last_error = str(exc)
                self.report_status(False, f"RealSense stream error: {exc}")
                if "No device connected" in self.last_error:
                    self.running.clear()
                    self.gateway.camera_started = False
                    return
                time.sleep(2.0)
            finally:
                if self.pipeline:
                    try:
                        self.pipeline.stop()
                    except Exception:
                        pass
            self.pipeline = None

    def start_pipeline(self, rs):
        last_error = None
        for fps in self.fps_candidates():
            pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, fps)
            config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, fps)
            try:
                pipeline.start(config)
                return pipeline, fps
            except Exception as exc:
                last_error = exc
                try:
                    pipeline.stop()
                except Exception:
                    pass
        raise last_error or RuntimeError("No RealSense stream profile available")

    def fps_candidates(self):
        candidates = [self.fps, 30, 15, 6]
        return list(dict.fromkeys(fps for fps in candidates if fps > 0))

    def capture_loop(self, cv2, np, pipeline):
        while self.running.is_set() and self.gateway.running.is_set():
            frames = pipeline.poll_for_frames()
            if not frames:
                time.sleep(0.002)
                continue
            if self.align:
                frames = self.align.process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame:
                continue
            now = time.time()
            frame = np.asanyarray(color_frame.get_data())
            if now - self.last_frame_time >= self.publish_interval:
                self.last_frame_time = now
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                if ok:
                    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
                    self.gateway.broadcast_camera({
                        "type": "camera_frame",
                        "format": "jpeg",
                        "encoding": "base64",
                        "width": self.width,
                        "height": self.height,
                        "time": now,
                        "data": payload,
                    })
            if self.pointcloud_supported and self.pointcloud_active.is_set() and depth_frame and now - self.last_pointcloud_time >= self.pointcloud_interval:
                self.last_pointcloud_time = now
                self.publish_pointcloud(np, frame, color_frame, depth_frame, now)

    def set_pointcloud_active(self, enabled):
        if not self.pointcloud_supported:
            self.report_pointcloud_status(False, "Point cloud is disabled")
            return False
        was_active = self.pointcloud_active.is_set()
        if enabled == was_active:
            return True
        if enabled:
            self.last_pointcloud_time = 0
            self.pointcloud_active.set()
            self.report_pointcloud_status(True, "Point cloud capture enabled")
        else:
            self.pointcloud_active.clear()
            self.report_pointcloud_status(False, "Point cloud capture paused")
        return True

    def publish_pointcloud(self, np, color_image, color_frame, depth_frame, now):
        if not self.pointcloud:
            return
        try:
            self.pointcloud.map_to(color_frame)
            points = self.pointcloud.calculate(depth_frame)
            vertices = np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1, 3)
            texcoords = np.asanyarray(points.get_texture_coordinates()).view(np.float32).reshape(-1, 2)
        except Exception as exc:
            self.report_pointcloud_status(False, f"Point cloud error: {exc}")
            return

        valid = np.isfinite(vertices[:, 2]) & (vertices[:, 2] > 0)
        indices = np.flatnonzero(valid)
        if indices.size == 0:
            self.report_pointcloud_status(False, "Point cloud has no valid depth points")
            return
        if indices.size > self.pointcloud_max_points:
            step = max(1, indices.size // self.pointcloud_max_points)
            indices = indices[::step][:self.pointcloud_max_points]

        sampled_vertices = vertices[indices]
        sampled_texcoords = texcoords[indices]
        color_height, color_width = color_image.shape[:2]
        u = np.clip((sampled_texcoords[:, 0] * color_width).astype(np.int32), 0, color_width - 1)
        v = np.clip((sampled_texcoords[:, 1] * color_height).astype(np.int32), 0, color_height - 1)
        bgr = color_image[v, u]

        point_data = np.empty((len(sampled_vertices), 6), dtype=np.float32)
        point_data[:, :3] = sampled_vertices
        point_data[:, 3] = bgr[:, 2]
        point_data[:, 4] = bgr[:, 1]
        point_data[:, 5] = bgr[:, 0]

        self.gateway.broadcast_pointcloud({
            "type": "pointcloud_frame",
            "format": "xyzrgb_float32",
            "encoding": "binary",
            "width": depth_frame.get_width(),
            "height": depth_frame.get_height(),
            "count": len(sampled_vertices),
            "stride": 6,
            "time": now,
        }, point_data.tobytes())

    def report_pointcloud_status(self, ok, message):
        self.gateway.broadcast({
            "type": "pointcloud_status",
            "ok": ok,
            "message": message,
            "time": time.time(),
        })
        print(message, flush=True)

    def report_status(self, ok, message):
        self.gateway.broadcast({
            "type": "camera_status",
            "ok": ok,
            "message": message,
            "time": time.time(),
        })
        print(message, flush=True)


class WebSocketClient:
    def __init__(self, sock, addr, server):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.alive = True
        self.camera_active = False
        self.lock = threading.Lock()

    def send_json(self, payload):
        self.send_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

    def send_text(self, text):
        self.send_frame(0x81, text.encode("utf-8"))

    def send_binary(self, data):
        self.send_frame(0x82, data)

    def send_pointcloud(self, metadata, data):
        header = self.frame_header(0x81, len(json.dumps(metadata, separators=(",", ":"), ensure_ascii=False).encode("utf-8")))
        text = json.dumps(metadata, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        binary_header = self.frame_header(0x82, len(data))
        with self.lock:
            if not self.alive:
                return
            try:
                self.sock.sendall(header + text + binary_header + data)
            except OSError:
                self.close()

    def send_frame(self, opcode, data):
        header = self.frame_header(opcode, len(data))
        with self.lock:
            if not self.alive:
                return
            try:
                self.sock.sendall(header + data)
            except OSError:
                self.close()

    def frame_header(self, opcode, length):
        if length < 126:
            return struct.pack("!BB", opcode, length)
        if length <= 0xFFFF:
            return struct.pack("!BBH", opcode, 126, length)
        else:
            return struct.pack("!BBQ", opcode, 127, length)

    def read_frame(self):
        header = self._recv_exact(2)
        if not header:
            return None, None
        first, second = header
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]

        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, count):
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def close(self):
        if not self.alive:
            return
        self.alive = False
        self.server.remove_client(self)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class RobotGateway:
    def __init__(
        self,
        dog_ip,
        dog_port,
        listen_host,
        listen_port,
        web_root,
        mock=False,
        camera=True,
        pointcloud=True,
        camera_width=640,
        camera_height=480,
        camera_fps=24,
        camera_publish_fps=24,
        camera_jpeg_quality=45,
        pointcloud_fps=10,
        pointcloud_max_points=RealSenseStreamer.DEFAULT_POINTCLOUD_MAX_POINTS,
        status_initial_delay=5.0,
    ):
        self.dog_addr = (dog_ip, dog_port)
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.web_root = Path(web_root)
        self.mock = mock
        self.camera_enabled = camera
        self.pointcloud_enabled = pointcloud
        self.status_initial_delay = max(0.0, float(status_initial_delay))
        self.camera = RealSenseStreamer(
            self,
            width=camera_width,
            height=camera_height,
            fps=camera_fps,
            jpeg_quality=camera_jpeg_quality,
            publish_fps=camera_publish_fps,
            enable_pointcloud=pointcloud,
            pointcloud_fps=pointcloud_fps,
            pointcloud_max_points=pointcloud_max_points,
        ) if camera else None
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.camera_clients = set()
        self.pointcloud_clients = set()
        self.camera_started = False
        self.last_move_log_time = 0
        self.running = threading.Event()
        self.running.set()
        self.robot_ready = threading.Event()
        self.udp_lock = threading.Lock()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.settimeout(0.2)
        self.control_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_control_udp_client = None
        self.control_udp_lock = threading.Lock()
        self.status = {}
        self.imu = {}
        self.last_imu_time = 0
        self.last_imu_broadcast_time = 0
        self.last_udp_error = ""
        self.last_udp_error_time = 0
        self.velocity = {"frontback": 0.0, "leftright": 0.0, "turn": 0.0}
        self.velocity_lock = threading.Lock()
        self.last_velocity_sent = 0
        self.last_command = {}
        self.motion_mode_override = None
        self.motion_mode_override_until = 0
        self.recv_buffer = ""
        if self.mock:
            self.status = self.default_mock_status()
            self.imu = self.default_mock_imu()

    def start(self):
        mode = "MOCK" if self.mock else "REAL"
        print(f"Gateway mode: {mode}", flush=True)
        print(f"Robot UDP target: {self.dog_addr[0]}:{self.dog_addr[1]}", flush=True)
        print(f"Web console: http://{self.listen_host}:{self.listen_port}", flush=True)
        print(f"UDP control listen: {self.listen_host}:{self.listen_port}", flush=True)
        self.control_udp.bind((self.listen_host, self.listen_port))
        self.control_udp.settimeout(0.2)
        threading.Thread(target=self.control_udp_loop, daemon=True).start()
        if self.mock:
            self.robot_ready.set()
            print("Mock robot service is ready.", flush=True)
            threading.Thread(target=self.mock_update_loop, daemon=True).start()
        else:
            threading.Thread(target=self.robot_connect_loop, daemon=True).start()
        threading.Thread(target=self.velocity_keepalive_loop, daemon=True).start()
        self.http_loop()

    def stop(self):
        self.running.clear()
        if self.camera:
            self.camera.stop()
        if not self.mock and self.robot_ready.is_set():
            self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_DISABLE_IMU})
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            client.close()
        self.udp.close()
        self.control_udp.close()

    def send_udp(self, payload):
        if self.mock:
            return
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        with self.udp_lock:
            try:
                self.udp.sendto(data, self.dog_addr)
                return True
            except OSError as exc:
                self.report_udp_error(f"Robot UDP send failed: {exc}")
                return False

    def default_mock_status(self):
        return {
            "battery": 80,
            "battery_level": 80,
            "motion_mode": MODE_LYING_DOWN,
            "velocity_level": 2,
            "model": 0,
            "hardware_error": 0,
            "robot_number": "MOCK-DOG-001",
            "robot_type": "MockQuadruped",
            "software_version": "mock-1.0",
            "protocol_version": 1.0,
        }

    def default_mock_imu(self):
        return {
            "frame_id": "imu_link",
            "euler": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.8},
            "timestamp": time.time(),
        }

    def robot_connect_loop(self):
        self.broadcast_robot_status(False, "等待机器狗 UDP 服务")
        while self.running.is_set():
            try:
                if not self.wait_for_robot():
                    continue
                if not self.running.is_set():
                    return
                self.robot_ready.set()
                self.broadcast_robot_status(True, "机器狗 UDP 服务已连接")
                threading.Thread(target=self.udp_receive_loop, daemon=True).start()
                threading.Thread(target=self.status_query_loop, daemon=True).start()
                self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_ENABLE_IMU})
                return
            except OSError as exc:
                self.report_udp_error(f"Robot UDP connect failed: {exc}")
                time.sleep(1.0)

    def broadcast_robot_status(self, ok, message):
        self.broadcast({
            "type": "robot_status",
            "ok": ok,
            "message": message,
            "time": time.time(),
        })
        print(message, flush=True)

    def mock_update_loop(self):
        yaw = 0.0
        while self.running.is_set():
            yaw += self.velocity["turn"] * 0.12
            self.imu = {
                "frame_id": "imu_link",
                "euler": {
                    "roll": round(self.velocity["leftright"] * 0.08, 4),
                    "pitch": round(self.velocity["frontback"] * -0.08, 4),
                    "yaw": round(yaw, 4),
                },
                "angular_velocity": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": round(self.velocity["turn"], 4),
                },
                "linear_acceleration": {
                    "x": round(self.velocity["frontback"], 4),
                    "y": round(self.velocity["leftright"], 4),
                    "z": 9.8,
                },
                "timestamp": time.time(),
            }
            self.broadcast_snapshot()
            self.broadcast({"type": "imu", "imu": self.imu})
            time.sleep(1.0)

    def wait_for_robot(self):
        while self.running.is_set():
            with self.udp_lock:
                try:
                    self.udp.sendto(b"PING", self.dog_addr)
                except OSError as exc:
                    self.report_udp_error(f"Waiting for robot UDP service: {exc}")
                    time.sleep(1.0)
                    continue
            try:
                data, _ = self.udp.recvfrom(1024)
            except socket.timeout:
                print("Waiting for robot UDP service...", flush=True)
                time.sleep(1.0)
                continue
            if data == b"PONG":
                print("Robot UDP service is ready.", flush=True)
                return True
        return False

    def report_udp_error(self, message):
        now = time.time()
        if message == self.last_udp_error and now - self.last_udp_error_time < 5.0:
            return
        self.last_udp_error = message
        self.last_udp_error_time = now
        self.robot_ready.clear()
        self.broadcast_robot_status(False, message)

    def status_query_loop(self):
        last_imu_enable_time = 0
        last_imu_reset_time = 0
        if self.status_initial_delay > 0:
            print(f"Delay first status query for {self.status_initial_delay:.1f}s.", flush=True)
            deadline = time.time() + self.status_initial_delay
            while self.running.is_set() and time.time() < deadline:
                time.sleep(min(0.1, deadline - time.time()))
            if not self.running.is_set():
                return
        while self.running.is_set():
            self.send_udp({"msg_type": MSG_QUERY_REQUEST, "query_code": QUERY_REALTIME_STATUS})
            now = time.time()
            imu_age = now - self.last_imu_time
            if imu_age > 10.0 and now - last_imu_reset_time > 15.0:
                self.reset_imu_stream()
                last_imu_reset_time = now
                last_imu_enable_time = now
            elif imu_age > 3.0 and now - last_imu_enable_time > 5.0:
                self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_ENABLE_IMU})
                last_imu_enable_time = now
            self.broadcast_snapshot()
            time.sleep(1.0)

    def udp_receive_loop(self):
        while self.running.is_set():
            try:
                data, _ = self.udp.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            self.recv_buffer += data.decode("utf-8", errors="ignore")
            for message in self.extract_json_messages():
                self.handle_robot_message(message)

    def control_udp_loop(self):
        while self.running.is_set():
            try:
                data, addr = self.control_udp.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            self.last_control_udp_client = addr
            text = data.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                with self.udp_lock:
                    self.udp.sendto(data, self.dog_addr)
                continue

            if isinstance(message, dict) and "type" in message:
                self.handle_web_command(None, message)
            elif isinstance(message, dict):
                self.send_udp(message)
            self.send_control_udp({"type": "accepted", "message": message})

    def extract_json_messages(self):
        messages = []
        balance = 0
        start = None
        index = 0
        while index < len(self.recv_buffer):
            char = self.recv_buffer[index]
            if char == "{":
                if balance == 0:
                    start = index
                balance += 1
            elif char == "}":
                balance -= 1
                if balance == 0 and start is not None:
                    raw = self.recv_buffer[start:index + 1]
                    try:
                        messages.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
                    self.recv_buffer = self.recv_buffer[index + 1:]
                    index = -1
                    start = None
            index += 1
        return messages

    def handle_robot_message(self, message):
        msg_type = message.get("msg_type")
        if msg_type == MSG_QUERY_RESPONSE and message.get("query_code") == QUERY_REALTIME_STATUS:
            result = message.get("result", {})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}
            if isinstance(result, dict):
                result = self.normalize_status(result)
                self.status = result
                self.broadcast({"type": "status", "status": self.status})
        elif msg_type == MSG_COMMAND_RESPONSE:
            self.apply_command_response(message)
            self.broadcast({"type": "command_result", "result": message})
        elif msg_type == MSG_IMU_RESPONSE:
            self.imu = self.normalize_imu(message)
            now = time.time()
            self.last_imu_time = now
            if now - self.last_imu_broadcast_time >= 0.1:
                self.last_imu_broadcast_time = now
                self.broadcast({"type": "imu", "imu": self.imu})
        else:
            self.broadcast({"type": "robot", "message": message})
        self.send_control_udp(message)

    def normalize_imu(self, message):
        source = message.get("result", message)
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except json.JSONDecodeError:
                source = {}
        if not isinstance(source, dict):
            return {}
        normalized = dict(source)
        orientation = normalized.get("orientation")
        if isinstance(orientation, dict) and "euler" not in normalized:
            euler = self.quaternion_to_euler(orientation)
            if euler:
                normalized["euler"] = euler
        return normalized

    def quaternion_to_euler(self, orientation):
        try:
            w = float(orientation.get("w", 1.0))
            x = float(orientation.get("x", 0.0))
            y = float(orientation.get("y", 0.0))
            z = float(orientation.get("z", 0.0))
        except (TypeError, ValueError):
            return None
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2 * (w * y - z * x)
        pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return {"roll": roll, "pitch": pitch, "yaw": yaw}

    def normalize_status(self, status):
        normalized = dict(status)
        if self.motion_mode_override is not None and time.time() < self.motion_mode_override_until:
            normalized["motion_mode"] = self.motion_mode_override
        return normalized

    def handle_web_command(self, client, message):
        command_type = message.get("type")
        if command_type == "move":
            now = time.time()
            if now - self.last_move_log_time >= 1.0:
                print(f"Control move: {json.dumps(message, ensure_ascii=False)}", flush=True)
                self.last_move_log_time = now
        else:
            print(f"Control command: {json.dumps(message, ensure_ascii=False)}", flush=True)
        if command_type == "reset":
            self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_RESET})
            self.update_motion_mode(MODE_LYING_DOWN_WITHOUT_RESET)
        elif command_type == "stand":
            self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_STAND_UP})
            self.update_motion_mode(MODE_STANDING)
        elif command_type == "lie":
            self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_LIE_DOWN})
            self.update_motion_mode(MODE_LYING_DOWN)
        elif command_type == "emergency":
            self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_EMERGENCY_STOP})
        elif command_type == "stop":
            self.send_velocity(0, 0, 0)
        elif command_type == "move":
            self.send_velocity(
                clamp(message.get("frontback")),
                clamp(message.get("leftright")),
                clamp(message.get("turn")),
            )
        elif command_type == "model":
            self.send_udp({
                "msg_type": MSG_COMMAND_REQUEST,
                "cmd_code": CMD_SET_MOTION_MODEL,
                "para": 1 if int(message.get("value", 0)) else 0,
            })
            if self.mock:
                self.status["model"] = 1 if int(message.get("value", 0)) else 0
                self.broadcast({"type": "status", "status": self.status})
        elif command_type == "obstacle":
            self.send_udp({
                "msg_type": MSG_COMMAND_REQUEST,
                "cmd_code": CMD_ULTRASONIC_OBSTACLE,
                "para": 1 if message.get("enabled") else 0,
            })
        elif command_type == "action":
            self.send_udp({
                "msg_type": MSG_COMMAND_REQUEST,
                "cmd_code": CMD_PERFORM_ACTION,
                "para": int(message.get("code", 0)),
            })
        elif command_type == "video":
            self.send_udp({
                "msg_type": MSG_COMMAND_REQUEST,
                "cmd_code": CMD_CAMERA_STREAM,
                "para": 1 if message.get("enabled") else 0,
            })
        elif command_type == "imu_reset":
            self.reset_imu_stream()
            if client:
                client.send_json({"type": "imu_status", "ok": True, "message": "IMU stream reset requested"})
        elif command_type == "camera":
            if client:
                enabled = bool(message.get("enabled"))
                client.camera_active = enabled
                with self.clients_lock:
                    if enabled:
                        self.camera_clients.add(client)
                    else:
                        self.camera_clients.discard(client)
                if enabled:
                    self.ensure_camera_started()
                else:
                    self.stop_camera_if_idle()
        elif command_type == "pointcloud":
            enabled = bool(message.get("enabled"))
            if not self.pointcloud_enabled or not self.camera:
                if client:
                    client.send_json({"type": "pointcloud_status", "ok": False, "message": "Point cloud unavailable"})
            else:
                with self.clients_lock:
                    if enabled and client:
                        self.pointcloud_clients.add(client)
                    elif client:
                        self.pointcloud_clients.discard(client)
                    active = bool(self.pointcloud_clients)
                if enabled:
                    self.ensure_camera_started()
                self.camera.set_pointcloud_active(active)
                if not enabled:
                    self.stop_camera_if_idle()
        elif command_type == "ping":
            if client:
                client.send_json({"type": "pong", "time": time.time()})
        else:
            if client:
                client.send_json({"type": "error", "message": f"unknown command: {command_type}"})
            return

        self.last_command = message
        if command_type != "move":
            self.broadcast({"type": "sent", "command": message})
        if self.mock and command_type != "ping":
            self.broadcast({
                "type": "command_result",
                "result": {
                    "mock": True,
                    "result": 0,
                    "command": message,
                    "time": time.time(),
                },
            })

    def send_velocity(self, frontback, leftright, turn):
        velocity = {
            "frontback": round(frontback, 2),
            "leftright": round(leftright, 2),
            "turn": round(turn, 2),
        }
        with self.velocity_lock:
            self.velocity = velocity
        self.send_velocity_packet(velocity)

    def send_velocity_packet(self, velocity):
        self.last_velocity_sent = time.time()
        self.send_udp({
            "vel_move_frontback": velocity["frontback"],
            "vel_move_leftright": velocity["leftright"],
            "vel_turn_leftright": velocity["turn"],
        })

    def reset_imu_stream(self):
        self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_DISABLE_IMU})
        self.send_udp({"msg_type": MSG_COMMAND_REQUEST, "cmd_code": CMD_ENABLE_IMU})

    def velocity_keepalive_loop(self):
        while self.running.is_set():
            with self.velocity_lock:
                velocity = dict(self.velocity)
            moving = any(abs(value) >= 0.01 for value in velocity.values())
            if moving and time.time() - self.last_velocity_sent >= 0.08:
                self.send_velocity_packet(velocity)
            time.sleep(0.02)

    def apply_command_response(self, message):
        if not self.command_succeeded(message):
            return
        cmd_code = message.get("cmd_code")
        if cmd_code == CMD_RESET:
            self.update_motion_mode(MODE_LYING_DOWN_WITHOUT_RESET)
        elif cmd_code == CMD_STAND_UP:
            self.update_motion_mode(MODE_STANDING)
        elif cmd_code == CMD_LIE_DOWN:
            self.update_motion_mode(MODE_LYING_DOWN)

    def command_succeeded(self, message):
        result = message.get("result", message.get("ret", message.get("success", 0)))
        if isinstance(result, str):
            return result.lower() in ("0", "ok", "true", "success", "succeeded")
        if isinstance(result, bool):
            return result
        try:
            return int(result) == 0
        except (TypeError, ValueError):
            return True

    def update_motion_mode(self, motion_mode):
        self.motion_mode_override = motion_mode
        self.motion_mode_override_until = time.time() + 8.0
        self.status = dict(self.status) if isinstance(self.status, dict) else {}
        self.status["motion_mode"] = motion_mode
        self.broadcast({"type": "status", "status": self.status})

    def send_control_udp(self, payload):
        if not self.last_control_udp_client:
            return
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        with self.control_udp_lock:
            try:
                self.control_udp.sendto(data, self.last_control_udp_client)
            except OSError:
                pass

    def add_client(self, client):
        with self.clients_lock:
            self.clients.add(client)
        client.send_json({
            "type": "hello",
            "dog": "mock://quadruped" if self.mock else f"{self.dog_addr[0]}:{self.dog_addr[1]}",
            "mock": self.mock,
            "camera": self.camera_enabled,
            "pointcloud": self.pointcloud_enabled,
            "robot_ready": self.robot_ready.is_set(),
            "status": self.status,
            "imu": self.imu,
        })

    def remove_client(self, client):
        pointcloud_active = False
        with self.clients_lock:
            self.clients.discard(client)
            self.camera_clients.discard(client)
            self.pointcloud_clients.discard(client)
            pointcloud_active = bool(self.pointcloud_clients)
        if self.camera:
            self.camera.set_pointcloud_active(pointcloud_active)
            self.stop_camera_if_idle()

    def ensure_camera_started(self):
        if not self.camera:
            return
        if self.camera_started and self.camera.thread and self.camera.thread.is_alive():
            return
        self.camera_started = True
        self.camera.start()

    def stop_camera_if_idle(self):
        if not self.camera:
            return
        with self.clients_lock:
            active = bool(self.camera_clients or self.pointcloud_clients)
        if active:
            return
        self.camera_started = False
        self.camera.stop()

    def broadcast_snapshot(self):
        self.broadcast({
            "type": "snapshot",
            "status": self.status,
            "imu": self.imu,
            "clients": self.client_count(),
            "time": time.time(),
        })

    def broadcast(self, payload):
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            client.send_json(payload)

    def broadcast_camera(self, payload):
        with self.clients_lock:
            clients = [client for client in self.clients if client.camera_active]
        for client in clients:
            client.send_json(payload)

    def broadcast_pointcloud(self, metadata, data):
        with self.clients_lock:
            clients = [client for client in self.clients if client in self.pointcloud_clients]
        for client in clients:
            client.send_pointcloud(metadata, data)

    def client_count(self):
        with self.clients_lock:
            return len(self.clients)

    def http_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.listen_host, self.listen_port))
        server.listen(20)
        while self.running.is_set():
            try:
                sock, addr = server.accept()
            except OSError:
                break
            threading.Thread(target=self.handle_http_client, args=(sock, addr), daemon=True).start()

    def handle_http_client(self, sock, addr):
        try:
            request = self.read_http_request(sock)
            if not request:
                sock.close()
                return
            request_line, headers = request
            method, path, _ = request_line.split(" ", 2)
            if headers.get("upgrade", "").lower() == "websocket" and path.startswith("/ws"):
                self.accept_websocket(sock, addr, headers)
            elif method == "GET":
                self.serve_static(sock, path)
            else:
                self.send_response(sock, 405, "text/plain", b"Method Not Allowed")
        except Exception as exc:
            print(f"HTTP client error from {addr}: {exc}")
            try:
                sock.close()
            except OSError:
                pass

    def read_http_request(self, sock):
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 16384:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            data += chunk
        text = data.decode("iso-8859-1")
        lines = text.split("\r\n")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        return lines[0], headers

    def accept_websocket(self, sock, addr, headers):
        key = headers.get("sec-websocket-key")
        if not key:
            self.send_response(sock, 400, "text/plain", b"Missing Sec-WebSocket-Key")
            return
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        sock.sendall(response.encode("ascii"))
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        client = WebSocketClient(sock, addr, self)
        self.add_client(client)
        print(f"WebSocket connected: {addr[0]}:{addr[1]}")
        try:
            while client.alive:
                readable, _, _ = select.select([sock], [], [], 30)
                if not readable:
                    client.send_json({"type": "heartbeat", "time": time.time()})
                    continue
                opcode, payload = client.read_frame()
                if opcode is None or opcode == 0x8:
                    break
                if opcode == 0x9:
                    continue
                if opcode != 0x1:
                    continue
                try:
                    message = json.loads(payload.decode("utf-8"))
                except json.JSONDecodeError:
                    client.send_json({"type": "error", "message": "invalid json"})
                    continue
                self.handle_web_command(client, message)
        finally:
            print(f"WebSocket disconnected: {addr[0]}:{addr[1]}")
            client.close()

    def serve_static(self, sock, path):
        if path in ("", "/"):
            path = "/index.html"
        clean = os.path.normpath(path.lstrip("/"))
        if clean.startswith(".."):
            self.send_response(sock, 403, "text/plain", b"Forbidden")
            return
        file_path = self.web_root / clean
        if not file_path.exists() or not file_path.is_file():
            self.send_response(sock, 404, "text/plain", b"Not Found")
            return
        content_type = "text/html; charset=utf-8"
        if file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        self.send_file_response(sock, content_type, file_path)

    def send_file_response(self, sock, content_type, file_path):
        size = file_path.stat().st_size
        header = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {size}\r\n"
            "Connection: close\r\n\r\n"
        )
        try:
            sock.settimeout(2.0)
        except OSError:
            pass
        sock.sendall(header.encode("utf-8"))
        with file_path.open("rb") as handle:
            try:
                sock.sendfile(handle)
            except (AttributeError, OSError):
                while True:
                    chunk = handle.read(16384)
                    if not chunk:
                        break
                    sock.sendall(chunk)
        sock.close()

    def send_response(self, sock, status, content_type, body):
        reason = {
            200: "OK",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
        }.get(status, "OK")
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(header.encode("utf-8") + body)
        sock.close()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Quadruped WebSocket to UDP gateway")
    parser.add_argument("--dog-ip", default="192.168.96.2")
    parser.add_argument("--dog-port", type=int, default=8080)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=9001)
    parser.add_argument("--web-root", default=str(root / "web"))
    parser.add_argument("--mock", action="store_true", help="Run without a real robot and simulate status/IMU data")
    parser.add_argument("--no-camera", action="store_true", help="Disable direct RealSense RGB/depth streaming")
    parser.add_argument("--no-pointcloud", action="store_true", help="Do not advertise point cloud support")
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-fps", type=int, default=24)
    parser.add_argument("--camera-publish-fps", type=int, default=24)
    parser.add_argument("--camera-jpeg-quality", type=int, default=45)
    parser.add_argument("--pointcloud-fps", type=int, default=10)
    parser.add_argument("--pointcloud-max-points", type=int, default=RealSenseStreamer.DEFAULT_POINTCLOUD_MAX_POINTS)
    parser.add_argument("--status-initial-delay", type=float, default=5.0, help="Delay the first realtime status/battery query after robot UDP is ready")
    args = parser.parse_args()

    gateway = RobotGateway(
        dog_ip=args.dog_ip,
        dog_port=args.dog_port,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        web_root=args.web_root,
        mock=args.mock,
        camera=not args.no_camera,
        pointcloud=not args.no_pointcloud and not args.no_camera,
        camera_width=args.camera_width,
        camera_height=args.camera_height,
        camera_fps=args.camera_fps,
        camera_publish_fps=args.camera_publish_fps,
        camera_jpeg_quality=args.camera_jpeg_quality,
        pointcloud_fps=args.pointcloud_fps,
        pointcloud_max_points=args.pointcloud_max_points,
        status_initial_delay=args.status_initial_delay,
    )
    try:
        gateway.start()
    except KeyboardInterrupt:
        print("\nStopping gateway...")
    finally:
        gateway.stop()


if __name__ == "__main__":
    main()
