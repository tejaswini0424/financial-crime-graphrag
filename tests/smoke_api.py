"""Run against a running localhost API: python tests/smoke_api.py."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
import core
url='http://127.0.0.1:8010'
name='smoke-'+uuid.uuid4().hex
uid=None
try:
    r=requests.post(url+'/auth/register',json={'username':name,'password':'a'},timeout=20)
    assert r.status_code==201,r.text
    uid=r.json()['user_id']
    r=requests.post(url+'/auth/login',json={'username':name,'password':'a'},timeout=20);r.raise_for_status()
    headers={'Authorization':'Bearer '+r.json()['access_token']}
    assert len(requests.get(url+'/transactions',headers=headers,timeout=20).json())==256
    assert requests.get(url+'/transactions',timeout=20).status_code in [401,403]
    r=requests.post(url+'/investigate',headers=headers,json={'query':'Trace ACC-003 and ACC-005','hops':2},timeout=30)
    assert r.status_code==200,r.text
    assert r.json()['transactions'] and r.json()['sources']
    r=requests.post(url+'/cases',headers=headers,json={'title':'API smoke test','report':r.json()['summary']},timeout=20)
    assert r.status_code==201,r.text
    assert requests.post(url+'/auth/logout',headers=headers,timeout=20).status_code==200
    assert requests.get(url+'/auth/me',headers=headers,timeout=20).status_code==401
    print('API smoke passed: registration, login, authorization, transactions, GraphRAG, cases, logout.')
finally:
    if uid:
        with core.Session() as s:
            for cls in [core.Transaction,core.Document,core.Case,core.Login]:s.query(cls).filter_by(user=uid).delete()
            s.query(core.User).filter_by(id=uid).delete();s.commit()
