"""Unit tests for insectcam/motion.py. They need numpy, which the Pi has:

  cd /opt/insectcam && python3 -m unittest discover -s /tmp/pi-zero-cam/tests -t /opt/insectcam
  (or, from software/pi-zero-cam on a computer with numpy: py -m unittest discover tests)
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam.motion import (MotionDetector, PREVIEW_HEIGHT, PREVIEW_WIDTH, THRESHOLD,  # noqa: E402
                              local_score, preview_from_luma)


def flat(value: int) -> np.ndarray:
    return np.full((PREVIEW_HEIGHT, PREVIEW_WIDTH), value, dtype=np.uint8)


class ScoreTests(unittest.TestCase):
    def test_identical_frames_score_zero(self):
        frame = np.random.default_rng(1).integers(0, 256, (PREVIEW_HEIGHT, PREVIEW_WIDTH), dtype=np.uint8)
        self.assertEqual(local_score(frame, frame), 0.0)

    def test_whole_frame_brightness_change_is_ignored(self):
        # Auto exposure or a passing cloud brightens everything: must not count as motion.
        self.assertEqual(local_score(flat(100), flat(140)), 0.0)

    def test_small_bright_object_in_one_tile_scores_high(self):
        before, after = flat(100), flat(100)
        after[0:15, 0:20] = 200  # fills exactly the top-left tile
        # One tile at +100, 47 tiles at 0: the whole-frame average shifts by 100/48 = 2 (truncated),
        # so the strongest tile is |100 - 2| = 98 per pixel.
        self.assertAlmostEqual(local_score(before, after), 98.0, places=3)

    def test_noise_stays_below_threshold(self):
        rng = np.random.default_rng(7)
        base = rng.integers(60, 180, (PREVIEW_HEIGHT, PREVIEW_WIDTH))
        a = np.clip(base + rng.integers(-2, 3, base.shape), 0, 255).astype(np.uint8)
        b = np.clip(base + rng.integers(-2, 3, base.shape), 0, 255).astype(np.uint8)
        self.assertLess(local_score(a, b), THRESHOLD)

    def test_object_covering_a_tile_exceeds_threshold(self):
        before, after = flat(100), flat(100)
        after[30:45, 40:60] = 110  # a faint 10-level object over one tile
        self.assertGreaterEqual(local_score(before, after), THRESHOLD)


class PreviewTests(unittest.TestCase):
    def test_640x360_luma_is_block_averaged_to_160x90(self):
        luma = np.zeros((360, 640), dtype=np.uint8)
        luma[0:4, 0:4] = 80
        preview = preview_from_luma(luma)
        self.assertEqual(preview.shape, (PREVIEW_HEIGHT, PREVIEW_WIDTH))
        self.assertEqual(int(preview[0, 0]), 80)
        self.assertEqual(int(preview[0, 1]), 0)

    def test_too_small_is_refused(self):
        with self.assertRaises(ValueError):
            preview_from_luma(np.zeros((50, 100), dtype=np.uint8))


class DetectorTests(unittest.TestCase):
    def test_first_check_is_the_baseline_and_is_kept(self):
        detector = MotionDetector()
        self.assertEqual(detector.check(flat(100)), (True, -1.0))
        self.assertEqual(len(detector.recent), 0)

    def test_still_scene_is_not_kept_and_motion_is(self):
        detector = MotionDetector()
        detector.check(flat(100))
        keep, score = detector.check(flat(100))
        self.assertFalse(keep)
        self.assertEqual(score, 0.0)
        moved = flat(100)
        moved[30:45, 40:60] = 160
        keep, score = detector.check(moved)
        self.assertTrue(keep)
        self.assertGreaterEqual(score, THRESHOLD)
        self.assertEqual(list(detector.recent), [0.0, score])

    def test_each_check_compares_with_the_previous_one_not_the_baseline(self):
        detector = MotionDetector()
        detector.check(flat(100))
        moved = flat(100)
        moved[30:45, 40:60] = 160
        detector.check(moved)                 # motion appears
        keep, _ = detector.check(moved.copy())  # and then stays put
        self.assertFalse(keep)

    def test_recent_scores_keep_only_the_last_twenty(self):
        detector = MotionDetector()
        for _ in range(30):
            detector.check(flat(100))
        self.assertEqual(len(detector.recent), 20)


if __name__ == "__main__":
    unittest.main()
