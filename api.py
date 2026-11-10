from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from pathlib import Path
from fastapi.responses import HTMLResponse
import core

app=FastAPI(title='Financial Crime Intelligence API',version='1.0.0')
@app.get('/',response_class=HTMLResponse,include_in_schema=False)
def dashboard():
    return (Path(__file__).parent/'web'/'index.html').read_text(encoding='utf-8')
security=HTTPBearer()
class Credentials(BaseModel):
    username:str
    password:str
class Question(BaseModel):
    query:str
    account:str|None=None
    hops:int=2
    settings:dict|None=None
class Rules(BaseModel):
    high_value:float=50000
    split_limit:float=10000
    split_count:int=4
    rapid_hours:float=2
    volume_count:int=12
    beneficiary_count:int=5
def validate_rules(settings):
    if settings is None:return None
    rules=Rules(**settings).model_dump()
    if any(v<=0 for v in rules.values()):raise ValueError('Rule thresholds must be positive.')
    return rules
class Knowledge(BaseModel):
    title:str
    content:str
    source:str='User supplied'
class CaseInput(BaseModel):
    title:str
    report:str
class CaseStatus(BaseModel):
    status:str
def user(auth:HTTPAuthorizationCredentials=Depends(security)):
    try:return core.identity(auth.credentials)
    except ValueError as e:raise HTTPException(401,str(e))
@app.exception_handler(ValueError)
async def bad_request(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=400,content={'detail':str(exc)})
@app.get('/health')
def health():return {'status':'ok'}
@app.post('/auth/register',status_code=201)
def register(c:Credentials):return {'user_id':core.register(c.username,c.password)}
@app.post('/auth/login')
def login(c:Credentials):return {'access_token':core.login(c.username,c.password),'token_type':'bearer'}
@app.post('/auth/logout')
def logout(auth:HTTPAuthorizationCredentials=Depends(security)):
    core.logout(auth.credentials);return {'status':'logged out'}
@app.get('/auth/me')
def me(u=Depends(user)):return u
@app.get('/transactions')
def transactions(u=Depends(user)):return core.records(u['id']).to_dict('records')
@app.post('/transactions',status_code=201)
def add(rows:list[dict],u=Depends(user)):return {'added':core.add_transactions(u['id'],rows)}
@app.delete('/transactions/{transaction_id}')
def delete(transaction_id:str,u=Depends(user)):return {'deleted':core.delete_transaction(u['id'],transaction_id)}
@app.get('/detections')
def detections(u=Depends(user)):return core.detect(core.records(u['id']))
@app.post('/detections')
def configured_detections(r:Rules,u=Depends(user)):
    return core.detect(core.records(u['id']),validate_rules(r.model_dump()))
@app.post('/investigate')
def investigate(q:Question,u=Depends(user)):
    if not 1<=q.hops<=3:raise ValueError('Hops must be 1–3.')
    return core.investigate(u['id'],q.query,q.account,q.hops,validate_rules(q.settings))
@app.get('/knowledge')
def knowledge(u=Depends(user)):return core.documents(u['id'])
@app.post('/knowledge',status_code=201)
def add_knowledge(k:Knowledge,u=Depends(user)):
    core.add_document(u['id'],k.title,k.content,k.source);return {'status':'created'}
@app.get('/cases')
def cases(u=Depends(user)):return core.cases(u['id'])
@app.post('/cases',status_code=201)
def add_case(c:CaseInput,u=Depends(user)):return {'id':core.save_case(u['id'],c.title,c.report)}
@app.patch('/cases/{case_id}')
def update(case_id:int,c:CaseStatus,u=Depends(user)):
    core.update_case(u['id'],case_id,c.status);return {'status':c.status}
@app.get('/network')
def network(u=Depends(user)):
    d=core.records(u['id']);g=core.knowledge_graph(u['id'],d,core.detect(d))
    return {'nodes':[{'id':n,**a} for n,a in g.nodes(data=True)],'edges':[{'source':a,'target':b,**x} for a,b,x in g.edges(data=True)]}
