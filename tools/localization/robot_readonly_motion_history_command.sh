python2 - <<'PY'
from __future__ import print_function
import re, glob, json, os, time
paths=sorted(glob.glob('/home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063/base_control-2.log.[0-9]*'))
paths.append('/home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063/base_control-2.log')
pattern=re.compile(r'^\[rosout\]\[INFO\] (.*?): MEDICAL_RX_VALID mono=([0-9.]+) vx=([-0-9.]+) wz=([-0-9.]+)')
moving=[];count=0;first=None;last=None
for path in paths:
    with open(path,'rb') as handle:
        for line in handle:
            match=pattern.match(line)
            if not match:continue
            stamp,mono,vx,wz=match.groups();mono=float(mono);vx=float(vx);wz=float(wz)
            row=dict(time=stamp,mono=mono,vx=vx,wz=wz)
            if first is None:first=row
            last=row;count+=1
            if abs(vx)>.002:moving.append(row)
moving.sort(key=lambda r:r['mono'])
groups=[]
for row in moving:
    if not groups or row['mono']-groups[-1][-1]['mono']>.4:groups.append([])
    groups[-1].append(row)
summary=[dict(first=g[0],last=g[-1],duration=g[-1]['mono']-g[0]['mono'],
              count=len(g),min_vx=min(r['vx'] for r in g),max_vx=max(r['vx'] for r in g)) for g in groups]
serial=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)!=serial:continue
            with open('/proc/'+pid+'/comm','rb') as handle:name=handle.read().strip()
            owners.append(dict(pid=int(pid),comm=name,fd=os.path.basename(fd),device=serial))
        except (IOError,OSError):pass
print(json.dumps(dict(read_only=True,clock=time.time(),logs=paths,valid_rx=count,
    first=first,last=last,nonzero_linear_feedback_segments=summary,serial_owners=owners),indent=2))
PY
