#!/usr/bin/env python3
"""Analyze downloaded evidence only; no network, ROS or hardware access."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    sources = {}
    def load(name, structured=True):
        content = (args.directory / name).read_bytes()
        sources[name] = dict(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
        text = content.decode('utf-8')
        return json.loads(text) if structured else text
    pulse = load('medical-supervised-short-pulse-v3-20261011.json')
    watch = load('readonly-control-watch-20261011.json')
    raw = load('uncommanded-raw-evidence-v2.log', False)
    history_text = load('robot-motion-history.log', False)
    history, unused = json.JSONDecoder().raw_decode(history_text[history_text.index('\n{\n') + 1:])
    first, last = pulse['odom'][0], pulse['odom'][-1]
    yaw = pulse['yaw_samples'][0]['yaw']
    dx, dy = last['x'] - first['x'], last['y'] - first['y']
    true_controls = [row for row in watch['commands'] if row['topic'] != '/feedback_vel']
    rows = watch['odom']
    raw_rows = re.findall(r'MEDICAL_RX_VALID mono=([0-9.]+) vx=([-0-9.]+)', raw)
    positive = [row for row in pulse['commands'] if row['vx'] > 0]
    output = dict(
        status='INVESTIGATION_OPEN_BASE_DRIVER_STOPPED', sources=sources,
        physical_observation=dict(source='user', approximately_measured=True,
            total_forward_cm=30, planned_second_segment_cm=15,
            unexpected_first_segment_cm=15,
            first_segment_stage='Protection refusal investigation / repair-file upload',
            exact_wall_timestamp_unknown=True),
        scheduled_pulse=dict(status=pulse['status'], positive_commands=len(positive),
            zero_commands=sum(row['vx'] == 0 for row in pulse['commands']),
            first_to_last_positive_s=positive[-1]['t']-positive[0]['t'],
            main_positive_loop_s=pulse['positive_end']-pulse['positive_begin'],
            odom_forward_m=dx*math.cos(yaw)+dy*math.sin(yaw),
            odom_lateral_m=-dx*math.sin(yaw)+dy*math.cos(yaw),
            strict_stop=pulse['post_stop'], cleanup_errors=pulse['cleanup_errors']),
        subsequent_passive_watch=dict(duration_s=watch['duration_s'], odom_samples=len(rows),
            control_messages=len(true_controls), feedback_messages=len(watch['commands'])-len(true_controls),
            graph_snapshots=len(watch['graphs']), max_abs_vx=max(abs(row['vx']) for row in rows),
            max_abs_wz=max(abs(row['wz']) for row in rows),
            dx=rows[-1]['x']-rows[0]['x'], dy=rows[-1]['y']-rows[0]['y'],
            limitation='This later window does not exclude earlier transient commands or hardware faults.'),
        historical_feedback=dict(valid_rx=history['valid_rx'],
            segments=history['nonzero_linear_feedback_segments'],
            limitation='Feedback frames do not identify their cause or prove physical displacement.'),
        raw_excerpt=dict(valid_rx_lines=len(raw_rows),
            nonzero_linear_lines=sum(abs(float(vx)) > .002 for unused, vx in raw_rows)),
        readonly_robot_status=dict(base_node_absent='\n/base_control\n' not in raw,
            serial_owners_empty='SERIAL_OWNERS []' in raw,
            control_topic_absent='CONTROL_TOPIC_ABSENT_AFTER_DRIVER_STOP' in raw),
        conclusion='Unexpected physical movement confirmed by user; trigger not proven; do not resume floor driving.'
    )
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(dict(status=output['status'], output=str(args.output),
                         raw_rx_lines=len(raw_rows), passive_controls=len(true_controls))))


if __name__ == '__main__':
    main()
