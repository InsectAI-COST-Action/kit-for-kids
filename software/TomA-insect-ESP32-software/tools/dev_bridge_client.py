r"""Client for the firmware's serial development bridge (DevBridge).

Lets the SD card be inspected and changed while it stays inside the board,
over the same USB serial link used for flashing. Built for unattended
development sessions: normally a card change means physically moving the
card to a reader, which is not possible without someone present.

Only usable when the board is NOT actively capturing (DEV LS/CAT/PUT/RM/DF
are refused with "session active" while a session is running - see
DevBridge::execute in src/dev_bridge.cpp). Use `stop` first if a session is
running and unattended-safe shutdown is what you want; that reuses the same
finishSession()/SD.end() path the phone app's "Finish" button uses.

Usage:
  py tools\dev_bridge_client.py --port COM4 ls /
  py tools\dev_bridge_client.py --port COM4 ls /raw
  py tools\dev_bridge_client.py --port COM4 cat /raw/captures.csv
  py tools\dev_bridge_client.py --port COM4 get /config.json config.local.json
  py tools\dev_bridge_client.py --port COM4 put config.local.json /config.json
  py tools\dev_bridge_client.py --port COM4 rm /images/run_000001/shard_0001/stale.jpg.tmp
  py tools\dev_bridge_client.py --port COM4 df
  py tools\dev_bridge_client.py --port COM4 runs
  py tools\dev_bridge_client.py --port COM4 audit run_000041
  py tools\dev_bridge_client.py --port COM4 stop
  py tools\dev_bridge_client.py --port COM4 reboot
  py tools\dev_bridge_client.py --port COM4 ping
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("pyserial is required: py -m pip install pyserial", file=sys.stderr)
    raise SystemExit(1)

CHUNK_BYTES = 512


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 5.0):
        # This board's native USB-CDC wires DTR/RTS to the reset circuit -
        # the same lines esptool pulses to reset it for flashing. pyserial
        # asserts both by default the moment a port opens, which silently
        # rebooted the board (and restarted capture) on every single command
        # during testing. Constructing with the port unset, clearing both
        # lines, then opening avoids that pulse, so a bridge session can send
        # many commands against one running board without resetting it.
        self.serial = serial.Serial()
        self.serial.port = port
        self.serial.baudrate = baud
        self.serial.timeout = timeout
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.open()
        self.serial.reset_input_buffer()

    def close(self) -> None:
        self.serial.close()

    def _readline(self, overall_timeout: float = 5.0) -> str:
        # The per-call pyserial timeout stays short so a genuinely dead link
        # is reported promptly; this retries across that many short reads
        # instead of failing on the first quiet moment. That distinction
        # matters here specifically: PUT/CAT hold the firmware in a blocking
        # wait of up to kWriteTimeoutMs (20 s in src/dev_bridge.cpp) while a
        # transfer completes, which a single short read would misreport as a
        # dead board.
        deadline = time.monotonic() + overall_timeout
        while time.monotonic() < deadline:
            line = self.serial.readline()
            if line:
                return line.decode("utf-8", "replace").rstrip("\r\n")
        raise BridgeError(f"timed out waiting for a response ({overall_timeout:.0f}s)")

    def _expect_frame(self, overall_timeout: float = 5.0) -> str:
        """Reads until a <DEV ...> frame line, skipping ordinary log output.

        A <DEV PROGRESS ...> frame resets the deadline rather than counting
        towards it - it's the firmware actively confirming it's still
        working, not part of the actual reply. This is what makes a long,
        genuinely-working command distinguishable from a stalled one: see
        the AUDIT/CAT investigation in docs/dev-bridge.md, where the only
        way to tell the difference used to be guessing.
        """
        deadline = time.monotonic() + overall_timeout
        while True:
            remaining = max(0.5, deadline - time.monotonic())
            line = self._readline(overall_timeout=remaining)
            if line.startswith("<DEV PROGRESS ") and line.endswith(">"):
                print(f"  (progress) {line[14:-1].strip()}", file=sys.stderr)
                deadline = time.monotonic() + overall_timeout
                continue
            if line.startswith("<DEV ") and line.endswith(">"):
                return line[5:-1]
            # Non-frame lines are normal firmware logging; surface them so
            # nothing is silently swallowed, then keep waiting for the frame.
            if line.strip():
                print(f"  (log) {line}", file=sys.stderr)

    def command(self, line: str, timeout: float = 5.0) -> str:
        self.serial.write((f"DEV {line}\n").encode("utf-8"))
        return self._expect_frame(overall_timeout=timeout)

    def read_lines_until_end(self, timeout: float = 10.0) -> list[str]:
        """Reads payload lines until <DEV END>, treating <DEV PROGRESS ...>
        the same way _expect_frame does - see its docstring."""
        lines: list[str] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.5, deadline - time.monotonic())
            raw = self._readline(overall_timeout=remaining)
            if raw.startswith("<DEV PROGRESS ") and raw.endswith(">"):
                print(f"  (progress) {raw[14:-1].strip()}", file=sys.stderr)
                deadline = time.monotonic() + timeout
                continue
            if raw.startswith("<DEV END>"):
                return lines
            if raw.startswith("<DEV ERR"):
                raise BridgeError(raw[9:] if raw.startswith("<DEV ERR ") else "error")
            lines.append(raw)


def require_ok(frame: str) -> str:
    if not frame.startswith("OK"):
        raise BridgeError(frame)
    return frame[3:] if frame.startswith("OK ") else ""


def cmd_ping(bridge: Bridge, args: argparse.Namespace) -> None:
    require_ok(bridge.command("PING"))
    print("ok - board responding")


def cmd_stop(bridge: Bridge, args: argparse.Namespace) -> None:
    # finishSession() promotes the dashboard chunk and unmounts before the
    # firmware replies, observed taking ~12 s; give it real room.
    require_ok(bridge.command("STOP", timeout=30.0))
    print("stopped - card unmounted, safe to remove")


def cmd_reboot(bridge: Bridge, args: argparse.Namespace) -> None:
    require_ok(bridge.command("REBOOT"))
    print("reboot requested")


def cmd_mount(bridge: Bridge, args: argparse.Namespace) -> None:
    print(require_ok(bridge.command("MOUNT")))


def cmd_df(bridge: Bridge, args: argparse.Namespace) -> None:
    print(require_ok(bridge.command("DF")))


def cmd_ls(bridge: Bridge, args: argparse.Namespace) -> None:
    frame = bridge.command(f"LS {args.path}")
    payload = require_ok(frame)
    count = int(payload.split()[0]) if payload else 0
    lines = bridge.read_lines_until_end()
    for line in lines[:count]:
        print(line)


def cmd_cat(bridge: Bridge, args: argparse.Namespace) -> None:
    data = _read_file(bridge, args.path)
    sys.stdout.write(data.decode("utf-8", "replace"))


def cmd_get(bridge: Bridge, args: argparse.Namespace) -> None:
    data = _read_file(bridge, args.path)
    Path(args.destination).write_bytes(data)
    print(f"wrote {len(data)} bytes -> {args.destination}")


def _read_file(bridge: Bridge, path: str) -> bytes:
    frame = bridge.command(f"CAT {path}")
    payload = require_ok(frame)  # "<lines> bytes <total>"
    parts = payload.split()
    total = int(parts[2]) if len(parts) >= 3 else 0
    hex_lines = bridge.read_lines_until_end()
    hex_blob = "".join(hex_lines)
    data = bytes.fromhex(hex_blob)
    if len(data) != total:
        raise BridgeError(f"length mismatch: expected {total} bytes, got {len(data)}")
    return data


def cmd_put(bridge: Bridge, args: argparse.Namespace) -> None:
    data = Path(args.source).read_bytes()
    frame = bridge.command(f"PUT {args.path} {len(data)}")
    require_ok(frame)  # "send <n>"
    hex_blob = data.hex()
    # The ESP32-S3's native USB-CDC has a small receive ring buffer and no
    # hardware flow control - sending this in a few large bursts silently
    # overflowed it and dropped bytes, which the firmware could only see as
    # "payload never arrived" and eventually timed out on. Small writes with
    # a short pause let its receive loop drain between bursts.
    write_chunk = 64
    for start in range(0, len(hex_blob), write_chunk):
        bridge.serial.write(hex_blob[start:start + write_chunk].encode("ascii"))
        bridge.serial.flush()
        time.sleep(0.01)
    bridge.serial.write(b"\n")
    # Matches kWriteTimeoutMs in src/dev_bridge.cpp, with headroom: the
    # firmware hex-decodes and does an atomic write (temp file, flush,
    # rename) before replying, on top of receiving the payload itself.
    require_ok(bridge._expect_frame(overall_timeout=25.0))
    print(f"wrote {len(data)} bytes -> {args.path}")


def cmd_rm(bridge: Bridge, args: argparse.Namespace) -> None:
    require_ok(bridge.command(f"RM {args.path}"))
    print(f"removed {args.path}")


def cmd_audit(bridge: Bridge, args: argparse.Namespace) -> None:
    # captures.csv can be multi-MB by now; the firmware scans it locally and
    # replies with one summary line, which has been observed taking anywhere
    # from a few seconds to multiple minutes, or stalling outright (see
    # docs/dev-bridge.md - not yet root-caused). The firmware emits a
    # <DEV PROGRESS> heartbeat every 64 items (image-tree entries, then CSV
    # rows), which resets this timeout (see Bridge._expect_frame) - so this
    # only needs to cover the gap *between* heartbeats, not the whole scan,
    # and prints progress instead of sitting silent either way.
    print(require_ok(bridge.command(f"AUDIT {args.run_id}", timeout=60.0)))


def cmd_runs(bridge: Bridge, args: argparse.Namespace) -> None:
    frame = bridge.command("RUNS")
    payload = require_ok(frame)
    count = int(payload.split()[0]) if payload else 0
    lines = bridge.read_lines_until_end()
    for line in lines[:count]:
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM4")
    parser.add_argument("--baud", type=int, default=115200)
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("ping").set_defaults(func=cmd_ping)
    subparsers.add_parser("stop").set_defaults(func=cmd_stop)
    subparsers.add_parser("reboot").set_defaults(func=cmd_reboot)
    subparsers.add_parser("mount").set_defaults(func=cmd_mount)
    subparsers.add_parser("df").set_defaults(func=cmd_df)

    ls_parser = subparsers.add_parser("ls")
    ls_parser.add_argument("path")
    ls_parser.set_defaults(func=cmd_ls)

    cat_parser = subparsers.add_parser("cat")
    cat_parser.add_argument("path")
    cat_parser.set_defaults(func=cmd_cat)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("path")
    get_parser.add_argument("destination")
    get_parser.set_defaults(func=cmd_get)

    put_parser = subparsers.add_parser("put")
    put_parser.add_argument("source")
    put_parser.add_argument("path")
    put_parser.set_defaults(func=cmd_put)

    rm_parser = subparsers.add_parser("rm")
    rm_parser.add_argument("path")
    rm_parser.set_defaults(func=cmd_rm)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("run_id", help="e.g. run_000041")
    audit_parser.set_defaults(func=cmd_audit)

    subparsers.add_parser("runs").set_defaults(func=cmd_runs)

    args = parser.parse_args()
    bridge = Bridge(args.port, args.baud)
    try:
        args.func(bridge, args)
    except BridgeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        bridge.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
