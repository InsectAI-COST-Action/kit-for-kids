"""Motion detection for the Pi camera: the XIAO firmware's score, on the Pi's own frames.

Same method as ../TomA-insect-ESP32-software/src/motion_detector.cpp: take the
grayscale difference between two consecutive checks, subtract the whole-frame
brightness change (so auto-exposure and cloud shadows do not count), split the
frame into an 8 x 6 grid of tiles and score the strongest tile as its mean
absolute difference per pixel. A score at or above the threshold (5, fixed, as on
the XIAO) means "something moved". Using the same score and threshold keeps the
dashboard's motion panel and run records comparable across the two cameras.

Differences, all because the Pi streams low-resolution frames anyway:
  - the frame is the camera's 640x360 luma stream block-averaged to 160x90
    (the XIAO re-initialises its sensor to take a 160x120 grayscale frame);
  - nothing is re-initialised between checks, so autofocus, exposure and white
    balance are never reset.
"""

from __future__ import annotations

from collections import deque

import numpy as np

PREVIEW_WIDTH, PREVIEW_HEIGHT = 160, 90
TILE_COLUMNS, TILE_ROWS = 8, 6
TILE_WIDTH, TILE_HEIGHT = PREVIEW_WIDTH // TILE_COLUMNS, PREVIEW_HEIGHT // TILE_ROWS  # 20 x 15
THRESHOLD = 5
RECENT_SCORES = 20  # what the phone app's motion meter shows


def preview_from_luma(luma: np.ndarray) -> np.ndarray:
    """Block-average a luma plane whose size is a multiple of 160x90 (640x360 -> 4x4 blocks)."""
    height, width = luma.shape
    block_y, block_x = height // PREVIEW_HEIGHT, width // PREVIEW_WIDTH
    if block_y < 1 or block_x < 1:
        raise ValueError(f"luma plane {width}x{height} is smaller than the {PREVIEW_WIDTH}x{PREVIEW_HEIGHT} preview")
    trimmed = luma[: PREVIEW_HEIGHT * block_y, : PREVIEW_WIDTH * block_x]
    blocks = trimmed.reshape(PREVIEW_HEIGHT, block_y, PREVIEW_WIDTH, block_x)
    return blocks.mean(axis=(1, 3)).astype(np.uint8)


def local_score(previous: np.ndarray, current: np.ndarray) -> float:
    """The strongest tile's mean |brightness-compensated difference| per pixel."""
    difference = current.astype(np.int16) - previous.astype(np.int16)
    # Truncate toward zero like the firmware's integer division.
    brightness_change = int(int(difference.sum()) / difference.size)
    adjusted = np.abs(difference - brightness_change)
    tiles = adjusted.reshape(TILE_ROWS, TILE_HEIGHT, TILE_COLUMNS, TILE_WIDTH).sum(axis=(1, 3))
    return float(tiles.max()) / (TILE_WIDTH * TILE_HEIGHT)


class MotionDetector:
    def __init__(self, threshold: int = THRESHOLD) -> None:
        self.threshold = threshold
        self.previous: np.ndarray | None = None
        self.recent: deque[float] = deque(maxlen=RECENT_SCORES)

    def check(self, preview: np.ndarray) -> tuple[bool, float]:
        """Returns (keep this frame, score). The first check is the baseline: always kept, score -1."""
        if self.previous is None:
            self.previous = preview
            return True, -1.0
        score = local_score(self.previous, preview)
        self.previous = preview
        self.recent.append(score)
        return score >= self.threshold, score
