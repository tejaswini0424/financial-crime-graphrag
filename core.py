"""Local, tenant-isolated investigation services shared by API and dashboard."""
from __future__ import annotations
import hashlib, hmac, secrets, json, math, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
from sqlalchemy import create_engine, Column, String, Text, Float, Integer, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = None

ROOT = Path(__file__).parent
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # SQLAlchemy uses psycopg 3 for hosted Postgres connections.
    if database_url.startswith(('postgres://', 'postgresql://')):
        database_url = 'postgresql+psycopg://' + database_url.split('://', 1)[1]
elif os.environ.get('VERCEL'):
    raise RuntimeError('Set DATABASE_URL to a persistent Postgres database before deploying. Local SQLite is not persistent on Vercel.')
else:
    (ROOT / 'data').mkdir(exist_ok=True)
    database_url = 'sqlite:///' + str(ROOT / 'data/platform.db')
engine = create_engine(database_url, connect_args={'check_same_thread': False} if database_url.startswith('sqlite:') else {}, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()
class User(Base):
    __tablename__='users'
    id=Column(String, primary_key=True); username=Column(String, unique=True); password=Column(String)
class Login(Base):
    __tablename__='sessions'
    token=Column(String, primary_key=True); user=Column(String); expires=Column(String)
class Transaction(Base):
    __tablename__='transactions'
    id=Column(Integer, primary_key=True); user=Column(String, index=True)
    transaction_id=Column(String); sender_account=Column(String); receiver_account=Column(String)
    amount=Column(Float); transaction_date=Column(String); transaction_type=Column(String)
    location=Column(String); transaction_status=Column(String)
    __table_args__=(UniqueConstraint('user','transaction_id'),)
class Document(Base):
    __tablename__='documents'
    id=Column(Integer, primary_key=True); user=Column(String, index=True); title=Column(String); content=Column(Text); source=Column(String)
class Case(Base):
    __tablename__='cases'
    id=Column(Integer, primary_key=True); user=Column(String, index=True); title=Column(String); status=Column(String); report=Column(Text); created=Column(String)
Base.metadata.create_all(engine)
FIELDS=['transaction_id','sender_account','receiver_account','amount','transaction_date','transaction_type','location','transaction_status']
KNOWLEDGE=[
('AML • risk-based investigation','AML controls use customer context, source of funds, transaction purpose and proportionate monitoring. Rapid movement, circular transfers and unusual high value payments are leads requiring corroboration. These indicators do not establish criminal conduct.','https://www.fatf-gafi.org/en/topics/fatf-recommendations.html'),
('KYC • customer due diligence','Customer due diligence establishes customer identity, beneficial ownership, business purpose and expected activity. Review owners of linked accounts and common beneficiaries; shared ownership alone does not imply wrongdoing.','https://www.fatf-gafi.org/en/topics/fatf-recommendations.html'),
('STR • escalation and reporting','Document evidence and investigate suspicious transaction patterns, including splitting or structuring. Escalate to the designated compliance officer for jurisdiction-specific reporting assessment. A model score is not a legal determination and sample thresholds are not statutory limits.','https://www.fatf-gafi.org/en/topics/fatf-recommendations.html'),
('FATF • transaction monitoring','FATF Recommendations provide an international AML/CFT framework. Risk-based monitoring, record keeping, customer due diligence and suspicious transaction reporting support financial intelligence. Confirm current local requirements with official sources.','https://www.fatf-gafi.org/en/topics/fatf-recommendations.html')]

def register(username, password):
    if not username or not password: raise ValueError('Username and password must not be empty.')
    salt=secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    with Session() as s:
        if s.query(User).filter_by(username=username).first(): raise ValueError('Username already exists.')
        uid=secrets.token_hex(16); s.add(User(id=uid,username=username,password=salt+':'+digest)); s.commit()
    seed(uid)
    return uid

def login(username,password):
    with Session() as s:
        u=s.query(User).filter_by(username=username).first()
        if not u: raise ValueError('Invalid credentials.')
        salt,digest=u.password.split(':')
        if not hmac.compare_digest(digest,hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()): raise ValueError('Invalid credentials.')
        token=secrets.token_urlsafe(32)
        s.add(Login(token=hashlib.sha256(token.encode()).hexdigest(),user=u.id,expires=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat())); s.commit()
        return token

def identity(token):
    with Session() as s:
        t=s.get(Login,hashlib.sha256(token.encode()).hexdigest())
        if not t or datetime.fromisoformat(t.expires)<datetime.now(timezone.utc): raise ValueError('Session expired. Please log in.')
        u=s.get(User,t.user); return {'id':u.id,'username':u.username}

def logout(token):
    with Session() as s:
        t=s.get(Login,hashlib.sha256(token.encode()).hexdigest())
        if t: s.delete(t); s.commit()

def records(uid):
    with Session() as s:
        return pd.DataFrame([{k:getattr(t,k) for k in FIELDS} for t in s.query(Transaction).filter_by(user=uid)],columns=FIELDS)

def add_transactions(uid, rows):
    df=pd.DataFrame(rows)
    if not set(FIELDS)<=set(df.columns): raise ValueError('Required columns: '+', '.join(FIELDS))
    df=df[FIELDS].copy()
    if df.empty: raise ValueError('No transactions supplied.')
    if len(df)>50000: raise ValueError('Import up to 50,000 records at a time.')
    if df.isna().any().any(): raise ValueError('All fields are required; missing values found.')
    df['amount']=pd.to_numeric(df.amount,errors='raise')
    if not np.isfinite(df.amount).all() or (df.amount<=0).any(): raise ValueError('Amounts must be finite and greater than zero.')
    df['transaction_date']=pd.to_datetime(df.transaction_date,utc=True,errors='raise').dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    for k in set(FIELDS)-{'amount'}:
        df[k]=df[k].astype(str)
        if df[k].str.strip().eq('').any(): raise ValueError('Fields must not be blank.')
    if df.transaction_id.duplicated().any(): raise ValueError('Duplicate transaction IDs in import.')
    with Session() as s:
        existing={r[0] for r in s.query(Transaction.transaction_id).filter_by(user=uid)}
        if existing & set(df.transaction_id): raise ValueError('Transaction IDs already exist. Import cancelled.')
        s.add_all([Transaction(user=uid,**r) for r in df.to_dict('records')]); s.commit()
    return len(df)

def delete_transaction(uid,tid):
    with Session() as s:
        n=s.query(Transaction).filter_by(user=uid,transaction_id=tid).delete(); s.commit(); return n

def documents(uid):
    with Session() as s: return [dict(id=d.id,title=d.title,content=d.content,source=d.source) for d in s.query(Document).filter_by(user=uid)]
def add_document(uid,title,content,source):
    if not title.strip() or not content.strip(): raise ValueError('Title and content are required.')
    with Session() as s: s.add(Document(user=uid,title=title,content=content,source=source)); s.commit()

def seed(uid):
    rng=np.random.default_rng(42); now=datetime.now(timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0)
    rows=[]
    def row(a,b,amount,dt,kind='Transfer'):
        rows.append(dict(zip(FIELDS,[f'TX-{len(rows)+1:05}',a,b,float(amount),dt.isoformat(),kind,'Mumbai','Completed'])))
    for i in range(240):
        a,b=rng.choice([f'ACC-{j:03}' for j in range(1,31)],2,replace=False)
        row(a,b,round(float(rng.lognormal(7,0.65)),2),now-timedelta(days=int(rng.integers(2,31)),minutes=int(rng.integers(0,1440))),str(rng.choice(['Transfer','Card','Wire','Cash'])))
    for i in range(6): row('ACC-001','ACC-002',9200+i*50,now+timedelta(minutes=i*12))
    row('ACC-003','ACC-004',42000,now); row('ACC-004','ACC-005',41000,now+timedelta(minutes=25)); row('ACC-005','ACC-003',40000,now+timedelta(minutes=50))
    for j in range(6,12): row(f'ACC-{j:03}','ACC-030',15000,now+timedelta(minutes=j))
    row('ACC-012','ACC-029',180000,now,'Wire')
    add_transactions(uid,rows)
    for title,content,source in KNOWLEDGE: add_document(uid,title,content,source)

DEFAULTS=dict(high_value=50000.,split_limit=10000.,split_count=4,rapid_hours=2.,volume_count=12,beneficiary_count=5)
def detect(df,settings=None):
    cfg={**DEFAULTS,**(settings or {})}; findings=[]
    if df.empty: return findings
    d=df.copy(); d['dt']=pd.to_datetime(d.transaction_date,utc=True)
    # Only settled flows support movement hypotheses.
    d=d[d.transaction_status.str.lower().isin(['completed','settled','success'])].copy()
    def emit(account,cat,score,part,reason,action):
        if part.empty:return
        findings.append(dict(account_id=account,transaction_ids=part.transaction_id.tolist(),category=cat,risk_score=score,reason=reason,related_accounts=sorted(set(part.sender_account)|set(part.receiver_account)),recommended_action=action))
    for _,r in d[d.amount>=cfg['high_value']].iterrows(): emit(r.sender_account,'High-value transfer',70,d.loc[[r.name]],f'Amount {r.amount:,.2f} meets configured {cfg["high_value"]:,.2f} threshold.','Validate source of funds and expected customer activity.')
    for a,p in d.groupby('sender_account'):
        for day,q in p.groupby(p.dt.dt.date):
            small=q[(q.amount>=cfg['split_limit']*.8)&(q.amount<cfg['split_limit'])]
            if len(small)>=cfg['split_count']: emit(a,'Structuring / splitting',80,small,f'{len(small)} transfers near the illustrative split threshold on {day}.','Review business purpose and aggregation; threshold is not a legal reporting limit.')
            if len(q)>=cfg['volume_count']: emit(a,'Unusual volume',65,q,f'{len(q)} outgoing transfers in a UTC calendar day.','Compare with customer history and expected turnover.')
    for a in sorted(set(d.sender_account)&set(d.receiver_account)):
        pairs=[]
        for _,incoming in d[d.receiver_account==a].iterrows():
            out=d[(d.sender_account==a)&(d['dt']>incoming['dt'])&(d['dt']<=incoming['dt']+pd.Timedelta(hours=cfg['rapid_hours']))&(d.amount>=incoming.amount*.8)&(d.amount<=incoming.amount*1.2)]
            if not out.empty: pairs.extend([incoming.name,*out.index.tolist()])
        if pairs: emit(a,'Rapid movement / layering',85,d.loc[sorted(set(pairs))],f'Incoming funds followed by similarly sized outgoing transfers within {cfg["rapid_hours"]} hours.','Trace upstream and downstream parties and verify economic rationale.')
    g=nx.DiGraph()
    for _,r in d.iterrows():g.add_edge(r.sender_account,r.receiver_account)
    cycles=list(nx.simple_cycles(g,length_bound=3))[:100]
    for cycle in cycles:
        edges=set(zip(cycle,cycle[1:]+cycle[:1]))
        q=d[[ (r.sender_account,r.receiver_account) in edges for r in d.itertuples()]]
        emit(cycle[0],'Circular transfers',90,q,'Directed cycle of '+str(len(cycle))+' accounts; chronology and intent need review.','Check timestamps, ownership and legitimate settlement explanations.')
    for a,p in d.groupby('receiver_account'):
        if p.sender_account.nunique()>=cfg['beneficiary_count']:
            for day,q in p.groupby(p.dt.dt.date):
                if q.sender_account.nunique()>=cfg['beneficiary_count']:emit(a,'Common beneficiary',75,q,f'{q.sender_account.nunique()} distinct senders paid this beneficiary on {day}.','Establish beneficiary ownership and relationship to senders.')
    return findings

def network(df,findings):
    g=nx.MultiDiGraph(); risks={}
    for f in findings:
        risks[f['account_id']]=max(risks.get(f['account_id'],0),f['risk_score'])
    for r in df.to_dict('records'):
        g.add_edge(r['sender_account'],r['receiver_account'],key=r['transaction_id'],**r)
    for a in g:
        score=risks.get(a,0); g.nodes[a].update(risk_score=score,risk='High' if score>=75 else 'Medium' if score else 'Low')
    return g

def knowledge_graph(uid,df,findings):
    g=network(df,findings)
    for a in list(g):
        g.nodes[a]['kind']='Account'
        owner='OWNER-'+a; g.add_node(owner,kind='Organization' if int(hashlib.sha256(a.encode()).hexdigest()[:2],16)%2 else 'Individual',synthetic=True)
        g.add_edge(a,owner,relation='OWNED_BY'); g.add_edge(owner,a,relation='ASSOCIATED_WITH')
    for r in df.to_dict('records'):
        tid=r['transaction_id']; loc='LOCATION:'+r['location']
        g.add_node(tid,kind='Transaction');g.add_node(loc,kind='Location')
        g.add_edge(r['sender_account'],tid,relation='SENT_TO');g.add_edge(tid,r['receiver_account'],relation='RECEIVED_FROM');g.add_edge(tid,loc,relation='LOCATED_IN')
        b='BENEFICIARY:'+r['receiver_account'];g.add_node(b,kind='Beneficiary');g.add_edge(r['receiver_account'],b,relation='ASSOCIATED_WITH')
    docs=documents(uid)
    for doc in docs:g.add_node('DOC:'+str(doc['id']),kind='Regulatory document',title=doc['title'])
    for f in findings:
        p='PATTERN:'+f['category'];g.add_node(p,kind='Suspicious activity pattern');g.add_edge(f['account_id'],p,relation='FLAGGED_FOR')
        for doc in docs:
            if any(w in doc['content'].lower() for w in f['category'].lower().replace('/',' ').split() if len(w)>4):g.add_edge(p,'DOC:'+str(doc['id']),relation='REFERENCED_IN')
    return g

def investigate(uid,query,account=None,hops=2,settings=None):
    df=records(uid); fs=detect(df,settings); g=knowledge_graph(uid,df,fs); ng=network(df,fs)
    seeds=[a for a in ng if a.lower() in query.lower()]
    if account and account in ng:seeds.append(account)
    seeds=list(dict.fromkeys(seeds))
    if not seeds:
        relevant=[f for f in fs if any(w in f['category'].lower() for w in query.lower().split() if len(w)>3)]
        seeds=list(dict.fromkeys(f['account_id'] for f in (relevant or sorted(fs,key=lambda x:-x['risk_score']))))[:3]
    selected=set(seeds)
    undirected=ng.to_undirected()
    for a in seeds:selected.update(nx.single_source_shortest_path_length(undirected,a,cutoff=min(3,max(1,hops))))
    evidence=df[df.sender_account.isin(selected)&df.receiver_account.isin(selected)]
    leads=[f for f in fs if f['account_id'] in selected]
    context=set(selected)
    ug=g.to_undirected()
    for a in seeds:context.update(nx.single_source_shortest_path_length(ug,a,cutoff=min(3,max(1,hops))))
    relations=[dict(source=a,target=b,relation=x.get('relation','SENT_TO'),transaction_id=x.get('transaction_id')) for a,b,x in g.edges(data=True) if a in context and b in context]
    docs=documents(uid); passages=[]
    expanded=query+' '+' '.join(f['category']+' '+f['reason'] for f in leads)
    if docs:
        corpus=[d['title']+' '+d['content'] for d in docs]+[expanded]
        if TfidfVectorizer is not None:
            v=TfidfVectorizer(stop_words='english'); m=v.fit_transform(corpus); scores=cosine_similarity(m[-1],m[:-1]).ravel()
        else:
            # Equivalent lightweight TF-IDF/cosine fallback for the cloud bundle.
            import re
            from collections import Counter
            counts=[Counter(re.findall(r'\b[a-z][a-z0-9]+\b',text.lower())) for text in corpus]
            vocabulary=set().union(*(set(c) for c in counts))
            idf={w:math.log((1+len(counts))/(1+sum(w in c for c in counts)))+1 for w in vocabulary}
            vectors=[{w:n*idf[w] for w,n in c.items()} for c in counts]
            norms=[math.sqrt(sum(x*x for x in v.values())) or 1 for v in vectors]
            scores=np.array([sum(n*vectors[-1].get(w,0) for w,n in v.items())/(norms[i]*norms[-1]) for i,v in enumerate(vectors[:-1])])
        order=sorted(range(len(docs)),key=lambda i:float(scores[i])+.15*('DOC:'+str(docs[i]['id']) in context),reverse=True)[:3]
        passages=[{**docs[i],'relevance':round(float(scores[i]),3),'graph_linked':'DOC:'+str(docs[i]['id']) in context} for i in order]
    paths=[]
    if len(seeds)>1:
        try:paths=[nx.shortest_path(ng,seeds[0],seeds[1])]
        except nx.NetworkXNoPath:pass
    lines=['# Investigation brief',f'Question: {query}',f'Generated: {datetime.now(timezone.utc).isoformat()}', 'Mode: local evidence-grounded template synthesis (no external language model).',f'Anchor accounts: {", ".join(seeds) or "None"}. Traversal: {hops} hops.',f'Evidence: {len(evidence)} transactions linking {len(selected)} accounts; {len(leads)} rule-based leads. Amounts use synthetic demonstration currency units.','## Findings']
    for f in leads[:20]:lines.append(f'- {f["category"]} | {f["account_id"]} | score {f["risk_score"]}/100. {f["reason"]} Evidence: {", ".join(f["transaction_ids"][:12])}. Action: {f["recommended_action"]}')
    if not leads:lines.append('No configured rule produced a lead in the retrieved context. This does not establish absence of risk.')
    lines.append('## Knowledge context')
    for p in passages:lines.append(f'[{p["id"]}] {p["title"]}: {p["content"]} Reference: {p["source"]}')
    lines.extend(['## Limitations','Synthetic owner identities are illustrative, not inferred real ownership. Rule scores are heuristic investigation priorities, not probabilities or proof. Sample knowledge is an educational paraphrase, not current legal advice. Verify evidence, customer context and applicable official requirements before escalation.'])
    return dict(summary='\n\n'.join(lines),seeds=seeds,paths=paths,relationships=relations,transactions=evidence.to_dict('records'),sources=passages,findings=leads,graph_nodes=g.number_of_nodes(),graph_edges=g.number_of_edges())

def cases(uid):
    with Session() as s:return [dict(id=c.id,title=c.title,status=c.status,report=c.report,created=c.created) for c in s.query(Case).filter_by(user=uid)]
def save_case(uid,title,report):
    with Session() as s:
        c=Case(user=uid,title=title,status='Open',report=report,created=datetime.now(timezone.utc).isoformat());s.add(c);s.commit();return c.id
def update_case(uid,cid,status):
    if status not in ['Open','Reviewing','Closed']:raise ValueError('Invalid status.')
    with Session() as s:
        c=s.query(Case).filter_by(user=uid,id=cid).first()
        if not c:raise ValueError('Case not found.')
        c.status=status;s.commit()
