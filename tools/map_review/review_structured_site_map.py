#!/usr/bin/env python3
"""Inspect exported geometry and write a reproducible review, without ROS."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--previous-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    raw_path = args.raw_dir / 'medical-live-map-20261010.pgm'
    pgm_path = args.output_dir / 'site-geometry-candidate.pgm'
    annotation = json.loads((args.output_dir / 'site-annotations.json').read_text(encoding='utf-8'))
    raw, geometry = Image.open(raw_path).convert('L'), Image.open(pgm_path).convert('L')
    meta = annotation['map_metadata']
    assert raw.size == geometry.size == (meta['width'], meta['height'])
    assert set(annotation['windows']) == set('1234ABC')
    assert len(annotation['recognition_boards']) == 2
    polygons = [annotation['geometry']['outer_boundary_map_xy_m']] + annotation['geometry']['obstacle_polygons_map_xy_m']
    for polygon in polygons:
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            delta = [abs(p[i]-q[i]) for i in (0, 1)]
            assert (delta[0] < 1e-8) != (delta[1] < 1e-8), ('NON_AXIS_ALIGNED_EDGE', p, q)
    outer = polygons[0]
    assert abs(max(p[0] for p in outer)-min(p[0] for p in outer)-4.5) < 1e-8
    assert abs(max(p[1] for p in outer)-min(p[1] for p in outer)-4.5) < 1e-8
    for window in annotation['windows'].values():
        b = window['bounds_from_left_top_m']
        assert abs(b[2]-b[0]-.5) < 1e-8 and abs(b[3]-b[1]-.5) < 1e-8
        poly = window['polygon_map_xy_estimate_m']
        center = [(min(p[i] for p in poly)+max(p[i] for p in poly))/2 for i in (0, 1)]
        assert all(abs(center[i]-window['center_map_xy_estimate_m'][i]) < 1e-8 for i in (0, 1))
        assert not window['validated'] and window['yaw_rad'] is None
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(raw_path) == annotation['source_map_sha256']
    old = args.previous_dir / 'site-geometry-candidate.pgm'
    assert sha(pgm_path) == sha(old), 'Display update must retain occupancy and registration'
    report = {'status': 'OFFLINE_GEOMETRY_AND_COORDINATES_CHECKED',
              'source_map_sha256': sha(raw_path), 'candidate_map_sha256': sha(pgm_path),
              'previous_candidate_sha256': sha(old), 'occupancy_unchanged': True,
              'outer_size_m': [4.5, 4.5], 'resolution_m': meta['resolution'],
              'axis_aligned_edges': sum(len(p) for p in polygons),
              'window_labels': list(annotation['windows']), 'window_size_m': [.5, .5],
              'recognition_lines': len(annotation['recognition_boards']),
              'localization_map': 'original SLAM map; not changed',
              'registration_validated': False, 'robot_motion_sent': False}
    (args.output_dir / 'map-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    # Nearest-neighbor on the left preserves what was actually captured.
    canvas = Image.new('RGB', (1300, 760), '#f5f7fa')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 24)
    small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 19)
    draw.text((40, 22), '原始扫描地图（原样保留）', fill='#192536', font=font)
    draw.text((700, 22), '整理后的矢量场地图', fill='#192536', font=font)
    left = raw.resize((600, 594), Image.Resampling.NEAREST).convert('RGB')
    canvas.paste(left, (30, 90))
    right = Image.open(args.output_dir / 'site-annotated.png').convert('RGB')
    right.thumbnail((620, 665), Image.Resampling.LANCZOS)
    canvas.paste(right, (665, 66))
    draw.text((30, 702), '规则轮廓用于展示；与现场雷达的配准仍待核对。', font=small, fill='#536176')
    canvas.save(args.output_dir / 'map-before-after.png')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
