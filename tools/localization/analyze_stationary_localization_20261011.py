#!/usr/bin/env python3
"""Review downloaded zero-only localization evidence; no ROS or hardware."""
import argparse, hashlib, json, re, sys
from pathlib import Path
from medical_serial_zero_diagnostic_20261011 import frame_policy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical_robot/scripts/heading_fix'))
from medical_rx_protocol_20261009 import FeedbackParser, decode_odom

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('audit',type=Path)
    cli.add_argument('hardware_log',type=Path)
    cli.add_argument('capture',type=Path)
    cli.add_argument('output',type=Path)
    args=cli.parse_args()
    raw=args.audit.read_bytes()
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    capture=json.loads(args.capture.read_text(encoding='utf-8'))
    parser=FeedbackParser(); feedback=[]; faults=[]; tx_count=0
    for row in rows:
        event=row['event']
        if event=='TX_BEGIN':
            tx_count+=1
            try: frame_policy(bytes.fromhex(row['hex']),row['label'])
            except ValueError as exc: faults.append(dict(event='TX_POLICY_REPLAY_FAILURE',error=str(exc)))
        if event=='RX_BYTES':
            for frame in parser.feed(bytes.fromhex(row['hex'])):
                if frame[3]==0x0a: feedback.append(decode_odom(frame))
        if event in ('TX_BLOCKED_OR_FAILED','ZERO_ONLY_FEEDBACK_FAULT','ROS_NONZERO_REJECTED','STATIONARY_LOCALIZATION_ABORT'):
            faults.append(row)
        if event=='TX_END' and row.get('success') is not True: faults.append(row)
    exits=re.findall(r'^STATIONARY_LOCALIZATION_EXIT=(\d+)$',args.hardware_log.read_text(encoding='utf-8'),re.M)
    ready=[r for r in rows if r['event']=='STRICT_STATIONARY_LOCALIZATION_READY']
    final_windows=[r for r in rows if r['event']=='FINAL_STRICT_STATIONARY_STOP']
    ends=[r for r in rows if r['event']=='STATIONARY_LOCALIZATION_END']
    nonzero=[r for r in feedback if abs(r['vx'])>.002]
    passed=bool(exits==['0'] and ready and final_windows and final_windows[-1]['evidence']['passed'] and ends and ends[-1].get('startup_completed') and
                not ends[-1].get('diagnostic_fault') and not faults and not nonzero and feedback and
                parser.rejected==0 and parser.overflow==0 and
                capture.get('status')=='REINITIALIZED_NO_MOTION' and
                capture.get('baseline_stop',{}).get('passed') and capture.get('final_stop',{}).get('passed') and
                capture.get('view',{}).get('pose',{}).get('fresh'))
    report=dict(status='ZERO_ONLY_LOCALIZATION_CAPTURE_PASSED_AWAITING_PHYSICAL_OBSERVATION' if passed else 'REVIEW_REQUIRED',
        audit_sha256=hashlib.sha256(raw).hexdigest(),hardware_exit_codes=exits,
        tx_frames=tx_count,tx_policy_faults=faults,rx_odom_frames=len(feedback),
        rx_nonzero_linear_frames=nonzero,rx_parser_rejected=parser.rejected,rx_parser_overflows=parser.overflow,
        max_abs_raw_vx=max((abs(r['vx']) for r in feedback),default=None),
        max_abs_raw_wz=max((abs(r['wz']) for r in feedback),default=None),
        ready_stop=None if not ready else ready[-1]['evidence'],
        hardware_final_stop=None if not final_windows else final_windows[-1]['evidence'],
        stationary_window_resets=sum(r['event']=='STRICT_STATIONARY_WINDOW_RESET_WAITING' for r in rows),
        baseline_stop=capture.get('baseline_stop'),final_stop=capture.get('final_stop'),
        capture_status=capture.get('status'),capture_error=capture.get('error'),
        captured_pose=capture.get('view',{}).get('pose'),uncertainty=capture.get('view',{}).get('uncertainty'),
        amcl_messages=len(capture.get('amcl',[])),odom_messages=len(capture.get('odom',[])),
        physical_observation='AWAITING_USER',
        limitation='Finite zero-only capture. Driver closes after deadline; TF subsequently expires. Not ground-motion or navigation acceptance.')
    with args.output.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('status','hardware_exit_codes','tx_frames','rx_odom_frames','max_abs_raw_vx','capture_status','capture_error','captured_pose','uncertainty')},ensure_ascii=False))

if __name__=='__main__':main()
