#!/usr/bin/env python2
"""Exercise only the default non-motion interface. Refuse an enabled server."""
from __future__ import print_function
import argparse,json,os
try:
    from urllib2 import urlopen,Request,HTTPError
except ImportError:
    from urllib.request import urlopen,Request
    from urllib.error import HTTPError
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',required=True);a=p.parse_args()
config=json.load(urlopen(a.url+'/api/config',timeout=3));assert config['motion_enabled'] is False
rows=[]
def post(path,data,expected=200,token=True):
    headers={'Content-Type':'application/json','Origin':a.url,'X-Medical-Token':config['csrf'] if token else 'WRONG'}
    request=Request(a.url+path,json.dumps(data).encode('utf-8'),headers)
    try:r=urlopen(request,timeout=30);status=r.getcode()
    except HTTPError as exc:r=exc;status=exc.code
    result=json.load(r);assert status==expected,(path,status,result)
    rows.append(dict(path=path,status=status,error=result.get('error')));return result
route=post('/api/preview',dict(waypoints=config['preset'],radius=config['preset_radius_m']))
assert all(s['passed'] for s in route['screens'].values())
saved=post('/api/save',dict(id=route['id']))
download=json.load(urlopen(a.url+saved['url'],timeout=3));assert download['motion_enabled'] is False
for path in ('start','pause','resume','cancel'):
    result=post('/api/'+path,dict(id=route['id'],confirmed=True),400)
    assert result['error']=='FIELD_ACCEPTANCE_REQUIRED_NO_GOALS_SENT'
post('/api/preview',dict(waypoints=config['preset'],radius=.75),403,token=False)
job=json.load(urlopen(a.url+'/api/job',timeout=3));assert job['job'] is None
report=dict(status='PASSIVE_HTTP_REVIEW_PASSED',checks=rows,job=None,motion_enabled=False,
            downloaded_route_url=saved['url'],length_m=route['length_m'],physical_motion_sent=False)
with os.fdopen(os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
