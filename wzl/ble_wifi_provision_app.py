#!/usr/bin/env python3
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid

try:
    import dbus
    import dbus.exceptions
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib
except Exception as exc:
    print(f"Missing BLE dependencies: {exc}", file=sys.stderr)
    print("Install: sudo apt install bluez python3-dbus python3-gi network-manager", file=sys.stderr)
    sys.exit(2)

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"
AGENT_IFACE = "org.bluez.Agent1"

PROVISION_SERVICE_UUID = "0000a001-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_UUID = "0000a002-0000-1000-8000-00805f9b34fb"
COMMAND_UUID = "0000a003-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000a004-0000-1000-8000-00805f9b34fb"
WIFI_LIST_UUID = "0000a005-0000-1000-8000-00805f9b34fb"

CODE_OK = 0
CODE_PARAM_ERROR = 1001
CODE_BUSY = 1002
CODE_WIFI_SCAN_FAILED = 1003
CODE_WRONG_PASSWORD = 1004
CODE_CONNECT_TIMEOUT = 1005
CODE_WIFI_NOT_FOUND = 1006
CODE_SYSTEM_ERROR = 1007


def dbus_to_python(value):
    if isinstance(value, dbus.String):
        return str(value)
    if isinstance(value, dbus.Boolean):
        return bool(value)
    if isinstance(value, (dbus.Int16, dbus.Int32, dbus.Int64, dbus.UInt16, dbus.UInt32, dbus.UInt64)):
        return int(value)
    if isinstance(value, dbus.Byte):
        return int(value)
    if isinstance(value, dbus.Array):
        return [dbus_to_python(item) for item in value]
    if isinstance(value, dbus.Dictionary):
        return {dbus_to_python(key): dbus_to_python(item) for key, item in value.items()}
    return value


def text_to_dbus_bytes(text):
    return [dbus.Byte(byte) for byte in text.encode("utf-8")]


def run_command(command, timeout=35):
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def parse_bool(value):
    if isinstance(value, bool):
        return value, None
    if value is None:
        return False, None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True, None
        if normalized in ("0", "false", "no", "off", ""):
            return False, None
    return None, "hidden must be boolean"


def make_response(request_id, cmd, code=CODE_OK, msg="ok", data=None):
    return {
        "id": str(request_id or ""),
        "cmd": cmd,
        "code": int(code),
        "msg": msg,
        "data": data or {},
    }


def split_nmcli_line(line):
    fields = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


class WifiProvisioner:
    def __init__(self, iface="wlan0", dry_run=False, device_name="RoboDog", robot_port=9001, fw_version="1.0.0"):
        self.iface = iface
        self.dry_run = dry_run
        self.device_name = device_name
        self.robot_port = robot_port
        self.fw_version = fw_version
        self.connect_lock = threading.Lock()
        self.last_ssid = ""
        self.status = {
            "state": "idle",
            "ok": False,
            "message": "waiting for BLE Wi-Fi provisioning",
            "ssid": "",
            "ip": "",
            "time": time.time(),
        }

    def snapshot(self):
        current = dict(self.status)
        current["ip"] = self.current_ip()
        return current

    def status_payload(self):
        current = self.snapshot()
        wifi_state = 0
        if current["state"] == "connecting":
            wifi_state = 1
        elif current["state"] == "connected" or current["ip"]:
            wifi_state = 2
        elif current["state"] == "error":
            wifi_state = 3
        return {
            "sn": self.device_sn(),
            "deviceName": self.device_name,
            "wifiState": wifi_state,
            "connectedSsid": current.get("ssid", ""),
            "ip": current.get("ip", ""),
            "fwVersion": self.fw_version,
            "state": current.get("state", ""),
            "message": current.get("message", ""),
        }

    def device_info_payload(self):
        data = self.status_payload()
        data.update(
            {
                "serviceUuid": PROVISION_SERVICE_UUID,
                "deviceInfoUuid": DEVICE_INFO_UUID,
                "commandUuid": COMMAND_UUID,
                "notifyUuid": NOTIFY_UUID,
                "wifiListUuid": WIFI_LIST_UUID,
            }
        )
        return data

    def device_sn(self):
        suffix = hostname_suffix()
        return f"RD-{suffix}" if suffix else "RD-UNKNOWN"

    def validate_wifi_config(self, payload):
        if not isinstance(payload, dict):
            return None, CODE_PARAM_ERROR, "data must be object"

        ssid = str(payload.get("ssid", "")).strip()
        password = str(payload.get("password", ""))
        hidden, hidden_error = parse_bool(payload.get("hidden", False))
        auth = str(payload.get("auth", "") or "").strip().lower()

        if not ssid:
            return None, CODE_PARAM_ERROR, "ssid is required"
        if len(password) > 0 and len(password) < 8:
            return None, CODE_PARAM_ERROR, "wifi password must be at least 8 characters"
        if hidden_error:
            return None, CODE_PARAM_ERROR, hidden_error
        if auth and auth not in ("open", "wpa2", "wpa3"):
            return None, CODE_PARAM_ERROR, "auth must be open, wpa2 or wpa3"

        return {"ssid": ssid, "password": password, "hidden": hidden}, CODE_OK, "ok"

    def begin_config(self, config):
        ssid = config["ssid"]
        if not self.connect_lock.acquire(blocking=False):
            self.set_status(False, "error", "wifi provisioning task already running", ssid)
            return False
        self.set_status(False, "connecting", f"connecting to Wi-Fi: {ssid}", ssid)
        return True

    def finish_config(self, config):
        try:
            return self._connect_wifi(config["ssid"], config["password"], config["hidden"])
        finally:
            self.connect_lock.release()

    def _connect_wifi(self, ssid, password, hidden):
        if self.dry_run:
            time.sleep(0.5)
            self.last_ssid = ssid
            return CODE_OK, self.set_status(True, "connected", f"mock connected: {ssid}", ssid)

        command = ["nmcli", "device", "wifi", "connect", ssid, "ifname", self.iface]
        if password:
            command.extend(["password", password])
        if hidden:
            command.extend(["hidden", "yes"])

        try:
            code, stdout, stderr = run_command(command, timeout=45)
        except FileNotFoundError:
            return CODE_SYSTEM_ERROR, self.set_status(False, "error", "nmcli not found, install NetworkManager", ssid)
        except subprocess.TimeoutExpired:
            return CODE_CONNECT_TIMEOUT, self.set_status(False, "error", "wifi connect timeout", ssid)

        if code != 0:
            detail = stderr or stdout or "nmcli connect failed"
            lowered = detail.lower()
            error_code = CODE_SYSTEM_ERROR
            if "secrets were required" in lowered or "password" in lowered:
                error_code = CODE_WRONG_PASSWORD
            elif "no network with ssid" in lowered or "not found" in lowered:
                error_code = CODE_WIFI_NOT_FOUND
            return error_code, self.set_status(False, "error", detail, ssid)

        self.last_ssid = ssid
        ip_addr = self.current_ip()
        message = f"Wi-Fi connected: {ssid}"
        if ip_addr:
            message = f"{message}, IP {ip_addr}"
        return CODE_OK, self.set_status(True, "connected", message, ssid)

    def scan_wifi(self):
        if self.dry_run:
            return CODE_OK, "ok", [
                {"ssid": "HomeWiFi", "rssi": -45, "secure": True, "freq": 2412},
                {"ssid": "Office_5G", "rssi": -61, "secure": True, "freq": 5180},
            ]

        command = [
            "nmcli",
            "-t",
            "-f",
            "SSID,SIGNAL,SECURITY,FREQ",
            "device",
            "wifi",
            "list",
            "ifname",
            self.iface,
            "--rescan",
            "yes",
        ]
        try:
            code, stdout, stderr = run_command(command, timeout=15)
        except FileNotFoundError:
            return CODE_SYSTEM_ERROR, "nmcli not found, install NetworkManager", []
        except subprocess.TimeoutExpired:
            return CODE_WIFI_SCAN_FAILED, "wifi scan timeout", []

        if code != 0:
            return CODE_WIFI_SCAN_FAILED, stderr or stdout or "wifi scan failed", []

        networks = []
        seen = set()
        for line in stdout.splitlines():
            fields = split_nmcli_line(line)
            if len(fields) < 4:
                continue
            ssid = fields[0].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(fields[1] or "0")
            except ValueError:
                signal = 0
            try:
                freq = int(fields[3] or "0")
            except ValueError:
                freq = 0
            networks.append({"ssid": ssid, "rssi": int(signal / 2 - 100), "secure": bool(fields[2].strip()), "freq": freq})
        return CODE_OK, "ok", networks

    def clear_wifi(self):
        if self.dry_run:
            self.last_ssid = ""
            return CODE_OK, self.set_status(False, "idle", "mock wifi config cleared", "")

        try:
            run_command(["nmcli", "device", "disconnect", self.iface], timeout=10)
            code, stdout, stderr = run_command(["nmcli", "-t", "-f", "UUID,TYPE", "connection", "show"], timeout=10)
            if code != 0:
                return CODE_SYSTEM_ERROR, self.set_status(False, "error", stderr or "failed to list wifi connections")
            for line in stdout.splitlines():
                fields = split_nmcli_line(line)
                if len(fields) >= 2 and fields[1] == "802-11-wireless":
                    run_command(["nmcli", "connection", "delete", fields[0]], timeout=10)
        except FileNotFoundError:
            return CODE_SYSTEM_ERROR, self.set_status(False, "error", "nmcli not found, install NetworkManager")
        except subprocess.TimeoutExpired:
            return CODE_SYSTEM_ERROR, self.set_status(False, "error", "clear wifi timeout")

        self.last_ssid = ""
        return CODE_OK, self.set_status(False, "idle", "wifi config cleared", "")

    def restart_network(self):
        if self.dry_run:
            return CODE_OK, self.set_status(False, "idle", "mock network restarted", self.last_ssid)

        try:
            code, _, _ = run_command(["nmcli", "device", "reapply", self.iface], timeout=15)
            if code != 0:
                run_command(["nmcli", "device", "disconnect", self.iface], timeout=10)
                run_command(["nmcli", "device", "connect", self.iface], timeout=20)
        except FileNotFoundError:
            return CODE_SYSTEM_ERROR, self.set_status(False, "error", "nmcli not found, install NetworkManager")
        except subprocess.TimeoutExpired:
            return CODE_SYSTEM_ERROR, self.set_status(False, "error", "restart network timeout")

        return CODE_OK, self.set_status(False, "idle", "network restarted", self.last_ssid)

    def result_payload(self, status):
        return {
            "ssid": status.get("ssid", ""),
            "ip": status.get("ip", ""),
            "gateway": self.current_gateway(),
            "robotPort": self.robot_port,
        }

    def set_status(self, ok, state, message, ssid=""):
        self.status = {
            "state": state,
            "ok": ok,
            "message": message,
            "ssid": ssid,
            "ip": self.current_ip(),
            "time": time.time(),
        }
        print(json.dumps(self.status, ensure_ascii=False), flush=True)
        return self.snapshot()

    def current_ip(self):
        try:
            code, stdout, _ = run_command(["ip", "-4", "-o", "addr", "show", "dev", self.iface], timeout=3)
        except Exception:
            return ""
        if code != 0:
            return ""
        for token in stdout.split():
            if "/" in token and token.count(".") == 3:
                return token.split("/", 1)[0]
        return ""

    def current_gateway(self):
        try:
            code, stdout, _ = run_command(["ip", "route", "show", "default", "dev", self.iface], timeout=3)
        except Exception:
            return ""
        if code != 0:
            return ""
        parts = stdout.split()
        if "via" in parts:
            index = parts.index("via")
            if index + 1 < len(parts):
                return parts[index + 1]
        return ""


class Application(dbus.service.Object):
    PATH = "/com/quadruped/wifi_provision"

    def __init__(self, bus):
        self.path = self.PATH
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for characteristic in service.characteristics:
                response[characteristic.get_path()] = characteristic.get_properties()
        return response


class Service(dbus.service.Object):
    PATH_BASE = "/com/quadruped/wifi_provision/service"

    def __init__(self, bus, index, uuid_value, primary):
        self.path = self.PATH_BASE + str(index)
        self.uuid = uuid_value
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array([ch.get_path() for ch in self.characteristics], signature="o"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise dbus.exceptions.DBusException("Invalid interface")
        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid_value, flags, service):
        self.path = service.path + "/char" + str(index)
        self.uuid = uuid_value
        self.flags = flags
        self.service = service
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {GATT_CHRC_IFACE: {"Service": self.service.get_path(), "UUID": self.uuid, "Flags": self.flags}}

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise dbus.exceptions.DBusException("Invalid interface")
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        raise dbus.exceptions.DBusException("Read not supported")

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        raise dbus.exceptions.DBusException("Write not supported")


class NotifyCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, NOTIFY_UUID, ["notify"], service)
        self.notifying = False

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        self.notifying = False

    def notify(self, payload):
        if not self.notifying:
            return
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": text_to_dbus_bytes(json.dumps(payload, ensure_ascii=False))}, [])

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class WifiListCharacteristic(NotifyCharacteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, WIFI_LIST_UUID, ["read", "notify"], service)
        self.notifying = False
        self.last_payload = make_response("", "wifi_list", CODE_OK, "ok", {"list": []})

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return text_to_dbus_bytes(json.dumps(self.last_payload, ensure_ascii=False))

    def publish(self, payload):
        self.last_payload = payload
        self.notify(payload)


class DeviceInfoCharacteristic(Characteristic):
    def __init__(self, bus, index, service, provisioner):
        super().__init__(bus, index, DEVICE_INFO_UUID, ["read"], service)
        self.provisioner = provisioner

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return text_to_dbus_bytes(json.dumps(self.provisioner.device_info_payload(), ensure_ascii=False))


class CommandCharacteristic(Characteristic):
    def __init__(self, bus, index, service, provisioner, notify_ch, wifi_list_ch):
        super().__init__(bus, index, COMMAND_UUID, ["write", "write-without-response"], service)
        self.provisioner = provisioner
        self.notify_ch = notify_ch
        self.wifi_list_ch = wifi_list_ch

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        try:
            payload = json.loads(bytes(dbus_to_python(value)).decode("utf-8"))
        except Exception as exc:
            self.notify_ch.notify(make_response("", "error", CODE_PARAM_ERROR, f"invalid json: {exc}"))
            return

        if isinstance(payload, dict) and "cmd" not in payload and "ssid" in payload:
            payload = {"id": str(uuid.uuid4()), "cmd": "set_wifi", "data": payload}
        if not isinstance(payload, dict):
            self.notify_ch.notify(make_response("", "error", CODE_PARAM_ERROR, "request must be object"))
            return

        request_id = str(payload.get("id", ""))
        cmd = str(payload.get("cmd", "")).strip()
        data = payload.get("data", {})
        if not isinstance(data, dict):
            self.notify_ch.notify(make_response(request_id, f"{cmd}_resp", CODE_PARAM_ERROR, "data must be object"))
            return

        handlers = {
            "hello": self.handle_hello,
            "get_status": self.handle_get_status,
            "scan_wifi": self.handle_scan_wifi,
            "set_wifi": self.handle_set_wifi,
            "clear_wifi": self.handle_clear_wifi,
            "restart_network": self.handle_restart_network,
        }
        handler = handlers.get(cmd)
        if not handler:
            self.notify_ch.notify(make_response(request_id, f"{cmd}_resp", CODE_PARAM_ERROR, "unknown cmd"))
            return
        handler(request_id, data)

    def handle_hello(self, request_id, data):
        self.notify_ch.notify(
            make_response(request_id, "hello_resp", CODE_OK, "ok", {"deviceNonce": uuid.uuid4().hex[:8], "sessionId": uuid.uuid4().hex})
        )

    def handle_get_status(self, request_id, data):
        self.notify_ch.notify(make_response(request_id, "get_status_resp", CODE_OK, "ok", self.provisioner.status_payload()))

    def handle_scan_wifi(self, request_id, data):
        self.notify_ch.notify(make_response(request_id, "scan_wifi_resp", CODE_OK, "scanning"))

        def worker():
            code, msg, networks = self.provisioner.scan_wifi()
            payload = make_response(request_id, "wifi_list", code, msg, {"list": networks})
            GLib.idle_add(self.wifi_list_ch.publish, payload)
            GLib.idle_add(self.notify_ch.notify, payload)

        threading.Thread(target=worker, daemon=True).start()

    def handle_set_wifi(self, request_id, data):
        config, code, msg = self.provisioner.validate_wifi_config(data)
        if code != CODE_OK:
            self.notify_ch.notify(make_response(request_id, "set_wifi_resp", code, msg))
            return
        if not self.provisioner.begin_config(config):
            self.notify_ch.notify(make_response(request_id, "set_wifi_resp", CODE_BUSY, "wifi provisioning task already running"))
            return

        self.notify_ch.notify(make_response(request_id, "set_wifi_resp", CODE_OK, "accepted"))
        self.notify_ch.notify(make_response(request_id, "wifi_progress", CODE_OK, "connecting", {"step": 1, "desc": "connecting to ap"}))

        def worker():
            result_code, status = self.provisioner.finish_config(config)
            result_msg = "connected" if result_code == CODE_OK else status.get("message", "connect failed")
            payload = make_response(request_id, "wifi_result", result_code, result_msg, self.provisioner.result_payload(status))
            GLib.idle_add(self.notify_ch.notify, payload)

        threading.Thread(target=worker, daemon=True).start()

    def handle_clear_wifi(self, request_id, data):
        self.notify_ch.notify(make_response(request_id, "clear_wifi_resp", CODE_OK, "accepted"))

        def worker():
            code, status = self.provisioner.clear_wifi()
            payload = make_response(request_id, "clear_wifi_resp", code, status.get("message", ""), self.provisioner.status_payload())
            GLib.idle_add(self.notify_ch.notify, payload)

        threading.Thread(target=worker, daemon=True).start()

    def handle_restart_network(self, request_id, data):
        self.notify_ch.notify(make_response(request_id, "restart_network_resp", CODE_OK, "accepted"))

        def worker():
            code, status = self.provisioner.restart_network()
            payload = make_response(request_id, "restart_network_resp", code, status.get("message", ""), self.provisioner.status_payload())
            GLib.idle_add(self.notify_ch.notify, payload)

        threading.Thread(target=worker, daemon=True).start()


class Advertisement(dbus.service.Object):
    PATH_BASE = "/com/quadruped/wifi_provision/advertisement"

    def __init__(self, bus, index, local_name):
        self.path = self.PATH_BASE + str(index)
        self.local_name = local_name
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            LE_ADVERTISEMENT_IFACE: {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array([PROVISION_SERVICE_UUID], signature="s"),
                "LocalName": dbus.String(self.local_name),
                "Includes": dbus.Array(["tx-power"], signature="s"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException("Invalid interface")
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        print("BLE advertisement released", flush=True)


class AutoAcceptAgent(dbus.service.Object):
    PATH = "/com/quadruped/wifi_provision/agent"

    def __init__(self, bus):
        self.path = self.PATH
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        print("BLE pairing agent released", flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print(f"Auto-accepting BLE PIN request from {device}", flush=True)
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print(f"Auto-accepting BLE passkey request from {device}", flush=True)
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print(f"Auto-confirming BLE pairing from {device}, passkey {passkey:06d}", flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print(f"Auto-authorizing BLE device {device}", flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, service_uuid):
        print(f"Auto-authorizing BLE service {service_uuid} for {device}", flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        print("BLE pairing request cancelled", flush=True)


def find_adapter(bus, adapter_name=None):
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
    objects = manager.GetManagedObjects()
    for path, interfaces in objects.items():
        if GATT_MANAGER_IFACE not in interfaces or LE_ADVERTISING_MANAGER_IFACE not in interfaces:
            continue
        if adapter_name and not path.endswith("/" + adapter_name):
            continue
        return path
    return None


def set_adapter_powered(bus, adapter_path):
    props = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), DBUS_PROP_IFACE)
    props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))
    props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(1))


def register_auto_accept_agent(bus):
    agent = AutoAcceptAgent(bus)
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/org/bluez"), AGENT_MANAGER_IFACE)
    manager.RegisterAgent(agent.get_path(), "NoInputNoOutput")
    manager.RequestDefaultAgent(agent.get_path())
    print("BLE pairing agent registered: auto accept enabled", flush=True)
    return agent, manager


def hostname_suffix():
    name = socket.gethostname().strip() or "board"
    return "".join(ch for ch in name if ch.isalnum() or ch in "-_")[-10:]


def main():
    parser = argparse.ArgumentParser(description="BLE Wi-Fi provisioning service for quadruped App protocol")
    parser.add_argument("--adapter", default=os.environ.get("BLE_ADAPTER", "hci0"))
    parser.add_argument("--wifi-iface", default=os.environ.get("WIFI_IFACE", "wlan0"))
    parser.add_argument("--name", default=os.environ.get("BLE_NAME", f"RoboDog-{hostname_suffix()}"))
    parser.add_argument("--robot-port", type=int, default=int(os.environ.get("ROBOT_PORT", "9001")))
    parser.add_argument("--fw-version", default=os.environ.get("FW_VERSION", "1.0.0"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-auto-accept-pairing", action="store_true")
    args = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path = find_adapter(bus, args.adapter)
    if not adapter_path:
        print(f"Bluetooth adapter not found or unsupported: {args.adapter}", file=sys.stderr)
        sys.exit(1)

    set_adapter_powered(bus, adapter_path)
    pairing_agent = None
    pairing_agent_manager = None
    if not args.no_auto_accept_pairing:
        try:
            pairing_agent, pairing_agent_manager = register_auto_accept_agent(bus)
        except Exception as exc:
            print(f"BLE pairing auto-accept unavailable: {exc}", file=sys.stderr, flush=True)

    provisioner = WifiProvisioner(
        iface=args.wifi_iface,
        dry_run=args.dry_run,
        device_name=args.name,
        robot_port=args.robot_port,
        fw_version=args.fw_version,
    )
    app = Application(bus)
    service = Service(bus, 0, PROVISION_SERVICE_UUID, True)
    device_info_ch = DeviceInfoCharacteristic(bus, 0, service, provisioner)
    command_ch = CommandCharacteristic(bus, 1, service, provisioner, None, None)
    notify_ch = NotifyCharacteristic(bus, 2, service)
    wifi_list_ch = WifiListCharacteristic(bus, 3, service)
    command_ch.notify_ch = notify_ch
    command_ch.wifi_list_ch = wifi_list_ch
    service.add_characteristic(device_info_ch)
    service.add_characteristic(command_ch)
    service.add_characteristic(notify_ch)
    service.add_characteristic(wifi_list_ch)
    app.add_service(service)

    advertisement = Advertisement(bus, 0, args.name)
    gatt_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), LE_ADVERTISING_MANAGER_IFACE)
    loop = GLib.MainLoop()

    def on_registered():
        print(f"BLE Wi-Fi provisioning GATT registered on {args.adapter}", flush=True)
        print(f"Service UUID: {PROVISION_SERVICE_UUID}", flush=True)
        print(f"Command UUID: {COMMAND_UUID}", flush=True)
        print(f"Notify UUID: {NOTIFY_UUID}", flush=True)

    def on_advertised():
        print(f"BLE advertising as {args.name}", flush=True)

    def on_error(error):
        print(f"BLE registration failed: {error}", file=sys.stderr, flush=True)
        loop.quit()

    gatt_manager.RegisterApplication(app.get_path(), {}, reply_handler=on_registered, error_handler=on_error)
    ad_manager.RegisterAdvertisement(advertisement.get_path(), {}, reply_handler=on_advertised, error_handler=on_error)

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ad_manager.UnregisterAdvertisement(advertisement.get_path())
        except Exception:
            pass
        if pairing_agent and pairing_agent_manager:
            try:
                pairing_agent_manager.UnregisterAgent(pairing_agent.get_path())
            except Exception:
                pass


if __name__ == "__main__":
    main()
