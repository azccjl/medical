#!/bin/bash
set -e
test ! -e /home/EPRobot/medical-stationary-readonly-clock-server2-20261011.log
nohup timeout --signal=INT --kill-after=3s 35s python2 /home/EPRobot/medical_offline_clock.py server --bind 192.168.12.1 --allow-client 192.168.12.71 --port 18080 >/home/EPRobot/medical-stationary-readonly-clock-server2-20261011.log 2>&1 </dev/null &
task_server_pid=$!
echo READONLY_CLOCK_SERVER_PID=$task_server_pid
sleep 1
kill -0 "$task_server_pid"
cat /home/EPRobot/medical-stationary-readonly-clock-server2-20261011.log
