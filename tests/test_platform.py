import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uuid
import pytest
import core

@pytest.fixture
def uid():
    name='test-'+uuid.uuid4().hex
    uid=core.register(name,'x')
    yield uid,name
    with core.Session() as s:
        for cls in [core.Transaction,core.Document,core.Case,core.Login]:s.query(cls).filter_by(user=uid).delete()
        s.query(core.User).filter_by(id=uid).delete();s.commit()

def test_authentication(uid):
    user,name=uid
    token=core.login(name,'x');assert core.identity(token)['id']==user
    with pytest.raises(ValueError):core.login(name,'wrong')
    core.logout(token)
    with pytest.raises(ValueError):core.identity(token)
    with core.Session() as s:assert s.get(core.User,user).password!='x'

def test_detection_and_graphrag(uid):
    user,_=uid;d=core.records(user);fs=core.detect(d)
    assert len(d)==256
    assert {'Structuring / splitting','Rapid movement / layering','Circular transfers','Common beneficiary','High-value transfer'}<={f['category'] for f in fs}
    result=core.investigate(user,'Trace ACC-003 to ACC-005',hops=2)
    assert result['paths'][0][0]=='ACC-003'
    assert result['transactions'] and result['relationships'] and result['sources']
    assert any(r['relation']=='OWNED_BY' for r in result['relationships'])
    ids=set(d.transaction_id)
    assert all(set(f['transaction_ids'])<=ids for f in fs)

def test_validation_and_isolation(uid):
    user,_=uid;d=core.records(user);r=d.iloc[0].to_dict();r['transaction_id']='NEW'
    r['amount']=-1
    with pytest.raises(ValueError):core.add_transactions(user,[r])
    assert len(core.records(user))==256
    r['amount']=100;assert core.add_transactions(user,[r])==1
    with pytest.raises(ValueError):core.add_transactions(user,[r])
    assert core.records('another-user').empty
    assert core.delete_transaction('another-user','NEW')==0
    assert core.delete_transaction(user,'NEW')==1

def test_cases(uid):
    user,_=uid;cid=core.save_case(user,'Test','Evidence')
    with pytest.raises(ValueError):core.update_case('another-user',cid,'Closed')
    core.update_case(user,cid,'Closed');assert core.cases(user)[0]['status']=='Closed'

def test_cloud_retrieval_fallback(uid,monkeypatch):
    monkeypatch.setattr(core,'TfidfVectorizer',None)
    result=core.investigate(uid[0],'Trace circular transfers ACC-003',hops=2)
    assert result['transactions'] and result['sources']
    assert result['sources'][0]['relevance']>0
