"""Command-line tools.

M1: USB CDC echo round-trip test.
M4 will replace this with binary-protocol capture to CSV.
"""

import sys

import serial
from serial.tools import list_ports

PICO_VID = 0x2E8A  # Raspberry Pi


def find_port() -> str | None:
    """Return the first serial port whose USB VID is Raspberry Pi's."""
    for p in list_ports.comports():
        if p.vid == PICO_VID:
            return p.device
    return None


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    if not port:
        print("No Raspberry Pi device found (VID 0x2E8A). Pass the port explicitly.")
        return 1
    msg = b"picowatt-echo-test\r\n"
    with serial.Serial(port, 115200, timeout=2) as ser:
        ser.reset_input_buffer()
        ser.write(msg)
        ser.flush()
        rx = ser.read(len(msg))
    ok = rx == msg
    print(f"port={port}\nsent    ={msg!r}\nreceived={rx!r}\n{'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
