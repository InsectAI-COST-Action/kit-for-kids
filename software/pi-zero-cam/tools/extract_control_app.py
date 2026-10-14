"""Copy the phone control app page out of the ESP32 firmware for the Pi to serve.

The page lives as a C++ raw string (kControlAppHtml) in
../TomA-insect-ESP32-software/src/control_server.cpp. Extracting it, rather
than keeping a second copy by hand, means the Pi and the XIAO always serve the
same page, translations and wording. Run after changing that page:

  py tools\\extract_control_app.py
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE.parent / "TomA-insect-ESP32-software" / "src" / "control_server.cpp"
TARGET = HERE / "insectcam" / "control_app.html"


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    match = re.search(r'kControlAppHtml\[\] PROGMEM = R"HTML\((.*?)\)HTML"', text, re.DOTALL)
    if match is None:
        raise SystemExit(f"kControlAppHtml not found in {SOURCE}")
    TARGET.write_text(match.group(1), encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET} ({len(match.group(1))} characters) from {SOURCE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
