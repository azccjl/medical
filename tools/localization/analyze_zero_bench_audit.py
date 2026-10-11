#!/usr/bin/env python3
"""Offline replay of TX policy and RX CRC from a downloaded bench audit."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
from medical_serial_zero_diagnostic_20261011 import frame_policy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical_robot/scripts/heading_fix'))
from medical_rx_protocol_20261009 import FeedbackParser, decode_odom


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('audit', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    raw = args.audit.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    counts = collections.Counter(row['event'] for row in rows)
    parser = FeedbackParser()
    feedback = []
    faults = []
    tx_labels = collections.Counter()
    for row in rows:
        if row['event'] == 'TX_BEGIN':
            data = bytes.fromhex(row['hex'])
            tx_labels[row['label']] += 1
            try:
                frame_policy(data, row['label'])
            except ValueError as exc:
                faults.append(dict(event='REPLAY_TX_POLICY_FAILURE', row=row, error=str(exc)))
        elif row['event'] == 'RX_BYTES':
            for frame in parser.feed(bytes.fromhex(row['hex'])):
                if frame[3] == 0x0a:
                    decoded = decode_odom(frame)
                    decoded.update(mono=row['mono'], wall=row['wall'])
                    feedback.append(decoded)
        if row['event'] in ('TX_BLOCKED_OR_FAILED', 'ZERO_ONLY_FEEDBACK_FAULT', 'ROS_NONZERO_REJECTED'):
            faults.append(row)
        if row['event'] == 'TX_END' and row['success'] is not True:
            faults.append(row)
    begin = next(row for row in rows if row['event'] == 'BENCH_START')
    end = next((row for row in reversed(rows) if row['event'] == 'BENCH_END'), None)
    nonzero = [row for row in feedback if abs(row['vx']) > .002]
    report = dict(status='ZERO_ONLY_RECORDED_FEEDBACK_NO_LINEAR_MOTION' if
                  end and end['startup_completed'] and not end.get('diagnostic_fault') and not faults and feedback and not nonzero
                  else 'DIAGNOSTIC_REQUIRES_REVIEW',
                  audit_path=str(args.audit), audit_sha256=hashlib.sha256(raw).hexdigest(),
                  events=dict(counts), tx_labels=dict(tx_labels), tx_policy_faults=faults,
                  duration_including_cleanup_s=None if end is None else end['mono']-begin['mono'],
                  begin_wall=begin['wall'], end_wall=None if end is None else end['wall'],
                  end_diagnostic_fault=None if end is None else end.get('diagnostic_fault'),
                  rx_odom_frames=len(feedback), rx_parser_rejected_bytes=parser.rejected,
                  rx_parser_overflows=parser.overflow, rx_pending_bytes=len(parser.buffer),
                  max_abs_raw_vx=None if not feedback else max(abs(row['vx']) for row in feedback),
                  max_abs_raw_wz=None if not feedback else max(abs(row['wz']) for row in feedback),
                  rx_nonzero_linear_frames=nonzero,
                  cancelled_shutdown_queries=counts['TX_CANCELLED_SHUTDOWN'],
                  physical_observation='AWAITING_USER_OBSERVATION',
                  limitation='One bench zero-only run cannot prove cause or safe floor driving.')
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
