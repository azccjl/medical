#!/usr/bin/env python3
"""Offline correlation of upload-window markers with zero-only bench RX."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical_robot/scripts/heading_fix'))
from medical_rx_protocol_20261009 import FeedbackParser, decode_odom


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', type=Path)
    cli.add_argument('run', type=int)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    sources = {}
    def read(name):
        raw = (args.directory / name).read_bytes()
        sources[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        return raw
    audit = [json.loads(line) for line in read('medical-zero-bench-audit%d-20261011.jsonl' % args.run).splitlines()]
    begin = json.loads(read('medical-zero-bench-upload-window%d-20261011.json' % args.run))
    completed = json.loads(read('medical-zero-bench-upload-completed%d-20261011.json' % args.run))
    bench_start = next(row for row in audit if row['event'] == 'BENCH_START')
    bench_end = next(row for row in reversed(audit) if row['event'] == 'BENCH_END')
    parser = FeedbackParser()
    samples = []
    for row in audit:
        if row['event'] == 'RX_BYTES':
            for frame in parser.feed(bytes.fromhex(row['hex'])):
                if frame[3] == 0x0a:
                    sample = decode_odom(frame)
                    sample.update(wall=row['wall'], mono=row['mono'])
                    samples.append(sample)
    periods = {}
    boundaries = [('before_upload_window', bench_start['wall'], begin['wall']),
                  ('upload_window_including_ssh_overhead', begin['wall'], completed['wall']),
                  ('after_upload_window', completed['wall'], bench_end['wall'])]
    for name, first, last in boundaries:
        rows = [row for row in samples if first <= row['wall'] < last]
        periods[name] = dict(frames=len(rows), duration_wall_s=last-first,
            max_abs_vx=None if not rows else max(abs(row['vx']) for row in rows),
            nonzero_linear_frames=sum(abs(row['vx']) > .002 for row in rows),
            max_rx_gap_s=None if len(rows) < 2 else max(b['mono']-a['mono'] for a,b in zip(rows,rows[1:])))
    valid_overlap = bench_start['wall'] < begin['wall'] < completed['wall'] < bench_end['wall'] and completed['bench_end_seen'] is False
    files_match = len(completed['files']) == 2 and len({row['sha256'] for row in completed['files']}) == 1 and all(row['bytes'] == 68800 for row in completed['files'])
    report = dict(status='UPLOAD_WINDOW_OVERLAP_CONFIRMED' if valid_overlap and files_match else 'REVIEW_REQUIRED',
        run=args.run, sources=sources, periods=periods,
        upload_start_after_bench_start_s=begin['wall']-bench_start['wall'],
        upload_end_after_bench_start_s=completed['wall']-bench_start['wall'],
        uploaded_files=completed['files'], payload_executed=completed['payload_executed'],
        decoder_rejected_bytes=parser.rejected, decoder_overflows=parser.overflow,
        physical_observation='AWAITING_USER_OBSERVATION',
        limitation='Markers bracket uploads plus SSH overhead; same mitigated zero-only candidate, not the original driver. No firmware root-cause proof.')
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
