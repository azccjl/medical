#!/usr/bin/env python3
"""Hypothetical interleaving of local reference C source; no hardware access.

This is an illustration, not a trace or simulation of the installed MCU.
"""
import json
import struct
from medical_serial_zero_diagnostic_20261011 import frame_policy


def main():
    stop = bytes.fromhex('5a120101000000000000271003e800000067')
    query = bytes.fromhex('5a070109020020')
    frame_policy(stop, 'velocity')
    frame_policy(query, 'odom_query')
    shared_buffer = bytearray(100)
    shared_buffer[:len(stop)] = stop
    selected_case = shared_buffer[3]
    original_speed = struct.unpack('>h', bytes(shared_buffer[4:6]))[0] / 1000.0
    # Inject an interrupt AFTER switch selected case 0x01 but BEFORE it
    # reads buffer[4:6]. No assertion that this happened on the real car.
    shared_buffer[:len(query)] = query
    mixed_speed = struct.unpack('>h', bytes(shared_buffer[4:6]))[0] / 1000.0
    print(json.dumps(dict(status='HYPOTHETICAL_INTERLEAVING_ILLUSTRATION_ONLY',
        installed_firmware_identity_confirmed=False,
        actual_mcu_interleaving_observed=False,
        original_case=selected_case, original_target_m_s=original_speed,
        next_frame_case=shared_buffer[3],
        mixed_speed_bytes=list(shared_buffer[4:6]), hypothetical_target_m_s=mixed_speed,
        reference='20210520 bottom_uart.c:133-141; uart_input:88-116',
        limitation='CRC checks both frames before consumption; it does not prevent post-check shared-buffer replacement.')))


if __name__ == '__main__':
    main()
