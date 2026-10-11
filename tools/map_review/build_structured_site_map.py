#!/usr/bin/env python3
"""Render a rectified layout candidate and semantic overlay; never modify SLAM evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, default=repo.parent / 'medical-live-mapping-20261010')
    parser.add_argument('--output-dir', type=Path, default=repo.parent / 'medical-structured-map-20261011')
    args = parser.parse_args()
    src = args.source_dir / 'medical-live-map-20261010.pgm'
    raw = Image.open(src).convert('L')
    w, h = raw.size
    ox, oy, resolution = -3.206440, -0.726359, .05
    # Approximate SLAM wall center registration, NOT a surveyed transform.
    left, top, right, bottom = 4., 3., 94., 93.
    boxes = {
        '1': (0., 1.7, .5, 2.2), '2': (.9, 2.2, 1.4, 2.7),
        '3': (0., 2.7, .5, 3.2), '4': (.9, 3.2, 1.4, 3.7),
        'A': (3.1, 1.3, 3.6, 1.8), 'B': (4., .8, 4.5, 1.3),
        'C': (4., 1.8, 4.5, 2.3),
    }
    boards = {'识别板一': [(3.1, 3.7), (3.1, 4.5)],
              '识别板二': [(1.4, 0.), (1.4, .8)]}
    upper = [(2.25, .8), (3.1, .8), (3.1, 1.5), (2.25, 1.5)]
    lower = [(1.4, 2.3), (2.25, 2.3), (2.25, 3.), (3.1, 3.), (3.1, 3.7), (1.4, 3.7)]

    def grid(u, v):
        return left + u * 20, top + v * 20

    def map_xy(u, v):
        c, r = grid(u, v)
        return [round(ox + c * resolution, 6), round(oy + (h - r) * resolution, 6)]

    # Separate geometric occupancy candidate. Boxes and board lines are floor markings,
    # so they MUST NOT become occupied cells in the PGM.
    clean = Image.new('L', (w, h), 205)
    cd = ImageDraw.Draw(clean)
    cd.rectangle((left, top, right, bottom), fill=254, outline=0, width=2)
    for polygon in [upper, lower]:
        p = [grid(*q) for q in polygon]
        cd.polygon(p, fill=205)
        cd.line(p + [p[0]], fill=0, width=2)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    clean.save(args.output_dir / 'site-geometry-candidate.pgm')
    (args.output_dir / 'site-geometry-candidate.yaml').write_text(
        'image: site-geometry-candidate.pgm\nresolution: 0.050000\n'
        'origin: [-3.206440, -0.726359, 0.000000]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n', encoding='utf-8')

    # Supersampled semantic drawing, plus an SVG with truly straight vector lines.
    S, size, offset, factor = 3, (1100, 1180), (100, 105), 190
    im = Image.new('RGB', (size[0] * S, size[1] * S), '#f5f7fa')
    dr = ImageDraw.Draw(im)
    font_file = 'C:/Windows/Fonts/msyh.ttc'
    def font(n):
        return ImageFont.truetype(font_file, n * S)
    def screen(u, v):
        return ((offset[0] + factor * u) * S, (offset[1] + factor * v) * S)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1180" viewBox="0 0 1100 1180">',
           '<rect width="1100" height="1180" fill="#f5f7fa"/>',
           '<g font-family="Microsoft YaHei,Arial,sans-serif">']

    def polygon(p, fill, outline=None, width=3):
        coords = [screen(*q) for q in p]
        dr.polygon(coords, fill=fill)
        if outline:
            dr.line(coords + [coords[0]], fill=outline, width=width * S, joint='curve')
        pts = ' '.join('%.2f,%.2f' % (x / S, y / S) for x, y in coords)
        svg.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (pts, fill, outline or 'none', width))

    def line(p, color, width=4):
        coords = [screen(*q) for q in p]
        dr.line(coords, fill=color, width=width * S)
        pts = ' '.join('%.2f,%.2f' % (x / S, y / S) for x, y in coords)
        svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (pts, color, width))

    def text(u, v, value, n=24, color='#243247'):
        x, y = screen(u, v)
        dr.text((x, y), value, font=font(n), fill=color, anchor='mm')
        svg.append('<text x="%.2f" y="%.2f" text-anchor="middle" dominant-baseline="central" font-size="%d" fill="%s">%s</text>' % (x/S, y/S, n, color, value))

    polygon([(0, 0), (4.5, 0), (4.5, 4.5), (0, 4.5)], '#ffffff', '#18232e', 5)
    for p in [upper, lower]:
        polygon(p, '#cbd1d8', '#18232e', 5)
    for label, (x0,y0,x1,y1) in boxes.items():
        polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)], '#ecf8f1' if label in 'ABC' else '#fff3d8', '#309966' if label in 'ABC' else '#c58824', 3)
        text((x0+x1)/2, (y0+y1)/2, label, 43)
    for label, p in boards.items():
        line(p, '#7b48bd', 6)
    text(3.72, 4.08, '识别板一', 24, '#7b48bd')
    text(.62, .40, '识别板二', 24, '#7b48bd')
    text(2.78, 4.17, '起点', 25)
    text(2.25, -.32, '场地整理图 · 4.5 m × 4.5 m', 30)
    text(2.25, 4.95, '七个方框：窗口区域    紫色线：识别板位置', 22)
    text(2.25, 5.22, '外墙与挡板均已整理平直 · 位置按规则图估计，待实地标定', 20)
    svg.extend(['</g>', '</svg>'])
    im.resize(size, Image.Resampling.LANCZOS).save(args.output_dir / 'site-annotated.png')
    (args.output_dir / 'site-annotated.svg').write_text('\n'.join(svg), encoding='utf-8')
    manifest = {'status': 'STRUCTURED_LAYOUT_CANDIDATE_UNCALIBRATED',
                'schema_version': 2,
                'source_map_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                'map_metadata': {'width': w, 'height': h, 'resolution': resolution,
                                 'origin': [ox, oy, 0.]},
                'registration': {'left_col': left,'top_row': top,'right_col': right,'bottom_row': bottom},
                'geometry': {'outer_boundary_map_xy_m': [map_xy(*p) for p in [(0,0),(4.5,0),(4.5,4.5),(0,4.5)]],
                             'obstacle_polygons_map_xy_m': [[map_xy(*p) for p in poly] for poly in [upper, lower]],
                             'wall_width_m': .10},
                'geometry_source': 'Official 4.5 m layout dimensions, approximately registered to outer SLAM walls.',
                'monitor_source': 'Monitor contour omitted at user request; lower-right walls rectified to official layout. Raw SLAM source retained.',
                'semantic_note': 'Window squares and recognition lines are overlays, absent from occupancy PGM.',
                'windows': {k: {'bounds_from_left_top_m':list(b),
                               'polygon_map_xy_estimate_m': [map_xy(*p) for p in [(b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3])]],
                               'center_map_xy_estimate_m':map_xy((b[0]+b[2])/2,(b[1]+b[3])/2),'yaw_rad':None,'validated':False} for k,b in boxes.items()},
                'recognition_boards': {k:{'line_from_left_top_m':v,'line_map_xy_estimate_m':[map_xy(*p) for p in v],'viewing_pose':None,'validated':False} for k,v in boards.items()}}
    (args.output_dir / 'site-annotations.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(args.output_dir)


if __name__ == '__main__':
    main()
