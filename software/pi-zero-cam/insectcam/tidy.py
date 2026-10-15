"""Tidy the photo drive: python3 -m insectcam.tidy /srv/insectcam

Run by pi/insectcam-drive whenever the drive is mounted or about to be handed to
a computer, and by the capture service at the start of each session.
"""

from __future__ import annotations

import sys
from pathlib import Path

from insectcam.capture import Storage


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/srv/insectcam")
    print("[insectcam-tidy] " + Storage(root).tidy_root())
    return 0


if __name__ == "__main__":
    sys.exit(main())
