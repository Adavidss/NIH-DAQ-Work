"""
HPLCValveControl.py
Minimal driver for a VICI / Valco EUDB-C6UW two-position USB valve.

• Requires:  pip install pyserial
• Usage:
      python HPLCValveControl.py        # auto-detect (falls back to COM3)
      python HPLCValveControl.py COM7   # explicit port
"""

import sys, time
from serial import Serial
from serial.tools import list_ports


# -----------------------------------------------------------------------------
# Locate the valve’s virtual COM port
# -----------------------------------------------------------------------------
def find_vici_port() -> str:
    """Return the first FTDI/VICI-looking port or raise RuntimeError."""
    TAGS = ("VICI", "VALCO", "FTDI", "USB SERIAL")
    for p in list_ports.comports():
        if any(tag in p.description.upper() for tag in TAGS):
            return p.device
    raise RuntimeError("No VICI valve found; run with an explicit COM port.")


# -----------------------------------------------------------------------------
# Tiny convenience wrapper
# -----------------------------------------------------------------------------
class ViciValve:
    """Two-position (A/B) valve helper."""

    def __init__(self, port: str | None = None, baud: int = 9600):
        # Choose port: CLI arg ▸ auto-detect ▸ default COM3
        port = port or (find_vici_port() if not port else port) or "COM3"
        self.ser = Serial(port, baud, timeout=1)
        print(f"[connected] {port}")

    # -- low-level ------------------------------------------------------------
    def _cmd(self, cmd: str) -> str:
        """Send ASCII command + CR, return device echo/response."""
        self.ser.write(f"{cmd}\r".encode())
        return self.ser.readline().decode(errors="ignore").strip()

    # -- high-level -----------------------------------------------------------
    def where(self) -> str:                 # Current position (A/B)
        resp = self._cmd("CP")              # e.g. 'CPA'
        return resp[-1] if resp else "?"

    def goto(self, pos: str):               # Move to A or B, wait until done
        pos = pos.upper()
        if pos not in "AB": raise ValueError("pos must be 'A' or 'B'")
        self._cmd(f"GO{pos}")
        while "RUN" in self._cmd("STAT"):   # poll until movement stops
            time.sleep(0.1)
        print(f"[ok] at {self.where()}")

    def toggle(self):                       # Same as front-panel button
        self._cmd("TO")

    def close(self):
        self.ser.close(); print("[closed]")


# -----------------------------------------------------------------------------
# Demo when run directly
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port_arg = sys.argv[1] if len(sys.argv) > 1 else None
    valve = ViciValve(port_arg)
    try:
        print("Position:", valve.where())
        valve.goto("B"); time.sleep(2); valve.goto("A")
    finally:
        valve.close()