#!/bin/bash
exec >/tmp/medical-clock-dependencies-20261011.log 2>&1
python2 -c "import paramiko; print(paramiko.__version__)"
ss -ulnp | grep ':123 ' || true
date -u -Ins
