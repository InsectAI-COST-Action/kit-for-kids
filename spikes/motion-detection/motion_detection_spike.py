"""Read-only preview-frame motion-detection spike for camera-card sessions."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WIDTH, CHANGE_LEVEL, COLUMNS, ROWS = 160, 12, 8, 6
QUANTILES = (75, 90, 95, 98, 99)


def key(path: Path):
    return [int(piece) if piece.isdigit() else piece.lower() for piece in re.split(r'(\d+)', path.name)]


def small_gray(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('JPEG could not be decoded')
    height, width = image.shape
    image = cv2.resize(image, (WIDTH, max(1, round(height * WIDTH / width))), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(image, (3, 3), 0)


def score(previous, current):
    delta = current.astype(np.int16) - previous.astype(np.int16)
    absolute = np.abs(delta - int(np.median(delta))).astype(np.float32)
    height, width = absolute.shape
    tile_h, tile_w = max(1, height // ROWS), max(1, width // COLUMNS)
    local = max(float(absolute[top:top + tile_h, left:left + tile_w].mean())
                for top in range(0, height, tile_h) for left in range(0, width, tile_w))
    return float(absolute.mean()), float((absolute >= CHANGE_LEVEL).mean()), local


def run_session(session: Path, limit_per_session: int):
    images = sorted(session.rglob('*.jpg'), key=key)
    if limit_per_session > 0 and len(images) > limit_per_session:
        pair_indices = np.unique(np.linspace(1, len(images) - 1, min(limit_per_session, len(images) - 1), dtype=int))
    else:
        pair_indices = range(1, len(images))
    rows, errors = [], []
    for index in pair_indices:
        previous_path, current_path = images[index - 1], images[index]
        try:
            global_mae, changed_fraction, local_peak = score(small_gray(previous_path), small_gray(current_path))
            rows.append({'run_id': session.name, 'sequence': int(index + 1), 'capture_id': current_path.stem,
                         'image_path': str(current_path), 'global_mae': global_mae,
                         'changed_fraction': changed_fraction, 'local_peak': local_peak})
        except Exception as error:
            errors.append(f'{current_path}: {error}')
    return rows, errors


def main():
    parser = argparse.ArgumentParser(description='Read-only motion spike; never writes to the card.')
    parser.add_argument('card_root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--limit-per-session', type=int, default=0, help='Use this many evenly distributed consecutive-frame pairs per session (0 means all).')
    args = parser.parse_args()
    card = args.card_root.resolve()
    sessions = sorted(path for path in (card / 'images').glob('run_*') if path.is_dir())
    if not sessions:
        raise SystemExit('No image sessions found under card images directory.')
    output = args.output or ROOT / 'artifacts' / f'motion-spike-{datetime.now():%Y%m%d-%H%M%S}'
    output.mkdir(parents=True, exist_ok=False)
    all_rows, all_errors, report = [], [], ['# Motion-detection spike', '', 'Read-only 160-pixel grayscale preview comparison. Global brightness shifts are compensated before scoring.', '']
    summary = {'card_root': str(card), 'preview_width': WIDTH, 'pixel_change_level': CHANGE_LEVEL, 'pairs_per_session_limit': args.limit_per_session, 'sessions': {}}
    for session in sessions:
        rows, errors = run_session(session, args.limit_per_session)
        all_rows.extend(rows)
        all_errors.extend(errors)
        values = np.asarray([row['local_peak'] for row in rows], dtype=np.float32)
        thresholds = {str(q): float(np.percentile(values, q)) for q in QUANTILES} if len(values) else {}
        retained = {q: int((values >= threshold).sum()) for q, threshold in thresholds.items()}
        top = sorted(rows, key=lambda row: row['local_peak'], reverse=True)[:24]
        summary['sessions'][session.name] = {'comparisons': len(rows), 'decode_errors': len(errors),
                                              'local_peak_quantiles': thresholds,
                                              'would_retain_at_quantile': retained, 'top_changes': top}
        report.extend([f'## {session.name}', '', f'- Comparisons: {len(rows)}', f'- Decode errors: {len(errors)}',
                       *[f'- {q}th percentile threshold {thresholds[q]:.3f}: retain {retained[q]} images.' for q in thresholds],
                       '- Top frame paths are recorded in summary.json and scores.csv.', ''])
        print(f'Processed {session.name}: {len(rows)} comparisons, {len(errors)} decode errors')
    with (output / 'scores.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=('run_id', 'sequence', 'capture_id', 'image_path', 'global_mae', 'changed_fraction', 'local_peak'))
        writer.writeheader()
        writer.writerows(all_rows)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (output / 'report.md').write_text('\n'.join(report), encoding='utf-8')
    (output / 'decode-errors.txt').write_text('\n'.join(all_errors) + ('\n' if all_errors else ''), encoding='utf-8')
    print(f'Read-only spike complete: {output}')


if __name__ == '__main__':
    main()
