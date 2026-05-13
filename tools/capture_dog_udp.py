#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import socket
import struct
from pathlib import Path


ETH_P_ALL = 0x0003
SOL_PACKET = 263
PACKET_ADD_MEMBERSHIP = 1
PACKET_MR_PROMISC = 1


def ipv4(addr):
    return socket.inet_ntoa(addr)


def main():
    parser = argparse.ArgumentParser(description="Capture quadruped UDP protocol packets")
    parser.add_argument("--iface", default="enP4p65s0")
    parser.add_argument("--dog-ip", default="192.168.96.2")
    parser.add_argument("--peer-ip", default="", help="Optional peer IP. Empty means any peer talking to dog-ip.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--out", default="captures/dog_udp_capture.jsonl")
    parser.add_argument("--no-promisc", action="store_true", help="Do not enable promiscuous mode.")
    parser.add_argument("--skip-imu", action="store_true", help="Do not print IMU packets to stdout.")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    sock.bind((args.iface, 0))
    if not args.no_promisc:
        ifindex = socket.if_nametoindex(args.iface)
        mreq = struct.pack("IHH8s", ifindex, PACKET_MR_PROMISC, 0, b"")
        sock.setsockopt(SOL_PACKET, PACKET_ADD_MEMBERSHIP, mreq)

    peer = args.peer_ip or "any"
    mode = "promisc" if not args.no_promisc else "normal"
    print(f"Capturing UDP {peer}<->{args.dog_ip}:{args.port} on {args.iface} ({mode})")
    print(f"Writing {out_path}")
    print("Press Ctrl+C to stop.")

    with out_path.open("a", encoding="utf-8") as output:
        while True:
            packet, _ = sock.recvfrom(65535)
            if len(packet) < 42:
                continue
            eth_type = struct.unpack("!H", packet[12:14])[0]
            if eth_type != 0x0800:
                continue

            ip_start = 14
            version_ihl = packet[ip_start]
            ihl = (version_ihl & 0x0F) * 4
            proto = packet[ip_start + 9]
            if proto != 17:
                continue

            src_ip = ipv4(packet[ip_start + 12:ip_start + 16])
            dst_ip = ipv4(packet[ip_start + 16:ip_start + 20])
            if args.dog_ip not in (src_ip, dst_ip):
                continue
            if args.peer_ip and {src_ip, dst_ip} != {args.dog_ip, args.peer_ip}:
                continue

            udp_start = ip_start + ihl
            src_port, dst_port, udp_len = struct.unpack("!HHH", packet[udp_start:udp_start + 6])
            if args.port not in (src_port, dst_port):
                continue

            payload = packet[udp_start + 8:udp_start + udp_len]
            text = payload.decode("utf-8", errors="replace")
            direction = "dog->board" if src_ip == args.dog_ip else "board->dog"
            record = {
                "time": dt.datetime.now().isoformat(timespec="milliseconds"),
                "direction": direction,
                "src": f"{src_ip}:{src_port}",
                "dst": f"{dst_ip}:{dst_port}",
                "text": text,
            }
            try:
                record["json"] = json.loads(text)
            except json.JSONDecodeError:
                pass

            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            if args.skip_imu and record.get("json", {}).get("msg_type") == 5:
                continue
            if "json" in record:
                print(f"{record['time']} {direction} {record['json']}")
            else:
                print(f"{record['time']} {direction} {text!r}")


if __name__ == "__main__":
    main()
