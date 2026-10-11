#!/bin/bash
exec >/tmp/medical-handshake-trace-20261011.log 2>&1
python2 /home/ncut/vm_connection_check_20261009.py 'sed -n "300410,300425p" /home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063/base_control-2.log'
