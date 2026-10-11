#!/usr/bin/env python3
"""Offline review of one supported-wheel pulse; no hardware or ROS access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from medical_supported_wheel_pulse_20261011 import frame_policy, forward_frame_policy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical_robot/scripts/heading_fix'))
from medical_rx_protocol_20261009 import FeedbackParser, decode_odom


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('audit', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    raw = args.audit.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    events = {row['event']: row for row in rows if row['event'] != 'TX_BEGIN'}
    parser = FeedbackParser()
    samples = []
    positives = []
    faults = []
    for row in rows:
        if row['event'] == 'TX_BEGIN':
            data = bytes.fromhex(row['hex'])
            forward = row['label'] == 'velocity' and any(data[4:10])
            try:
                if forward:
                    # Validate exact frame and phase; timing measured below.
                    forward_frame_policy(data,row['phase'],0.,1.)
                    positives.append(row)
                else: frame_policy(data,row['label'])
            except ValueError as exc:
                faults.append(dict(event='TX_REPLAY_POLICY_FAULT',row=row,error=str(exc)))
        if row['event'] in ('TX_BLOCKED_OR_FAILED','ZERO_ONLY_FEEDBACK_FAULT','WHEEL_RESPONSE_SPEED_LIMIT'):
            faults.append(row)
        if row['event'] == 'TX_END' and not row['success']: faults.append(row)
        if row['event'] == 'RX_BYTES':
            for frame in parser.feed(bytes.fromhex(row['hex'])):
                if frame[3] == 0x0a:
                    sample = decode_odom(frame)
                    sample.update(mono=row['mono'],wall=row['wall'])
                    samples.append(sample)
    start = events.get('AUTHORIZED_SUPPORTED_WHEEL_PULSE_BEGIN')
    end = events.get('AUTHORIZED_SUPPORTED_WHEEL_PULSE_END_ZERO_SENT')
    baseline = events.get('BASELINE_STRICT_STOP',{}).get('evidence')
    post = events.get('POST_PULSE_STRICT_STOP',{}).get('evidence')
    final = events.get('BENCH_END',{})
    success = bool(positives and baseline and baseline['passed'] and post and post['passed'] and
                   not faults and not final.get('diagnostic_fault'))
    report = dict(status='SUPPORTED_PULSE_AND_STRICT_FEEDBACK_STOP_PASSED' if success else 'REVIEW_REQUIRED',
        audit_sha256=hashlib.sha256(raw).hexdigest(), positive_tx_frames=len(positives),
        baseline_stop=baseline, post_stop=post, faults=faults,
        first_to_last_positive_tx_s=None if not positives else positives[-1]['mono']-positives[0]['mono'],
        first_positive_to_zero_record_s=None if not positives or not end else end['mono']-positives[0]['mono'],
        pulse_begin_wall=None if not start else start['wall'], pulse_end_wall=None if not end else end['wall'],
        rx_odom_frames=len(samples), max_abs_raw_vx=None if not samples else max(abs(s['vx']) for s in samples),
        rx_nonzero_linear_frames=sum(abs(s['vx'])>.002 for s in samples),
        rx_rejected_bytes=parser.rejected, rx_overflows=parser.overflow,
        diagnostic_fault=final.get('diagnostic_fault'),
        physical_observation='AWAITING_USER_OBSERVATION',
        limitation='Supported-wheel test only; not physical distance calibration or floor-navigation acceptance.')
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__': main()
