from datetime import datetime, timezone, timedelta
import html, json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import core

st.set_page_config(page_title='Financial Crime Intelligence',page_icon='◈',layout='wide')
st.markdown('''<style>
.stApp {background:#081321;color:#e5edf7} [data-testid="stSidebar"]{background:#101f32;border-right:1px solid #26374c}
h1,h2,h3 {letter-spacing:-.035em} .stButton>button,.stDownloadButton>button{border-radius:9px;border:1px solid #237f88}
[data-testid="stMetric"]{background:linear-gradient(135deg,#14283d,#102033);border:1px solid #254058;padding:18px;border-radius:14px}
[data-testid="stMetricValue"]{color:#50e4d1} .eyebrow{color:#50e4d1;letter-spacing:.2em;font-size:12px;font-weight:700}
.hero{padding:28px;background:linear-gradient(110deg,#102a40,#123c47);border:1px solid #23556a;border-radius:18px;margin-bottom:24px}
.muted{color:#a6b8cc} div[data-testid="stForm"]{border:1px solid #28425b;border-radius:16px;padding:24px}
</style>''',unsafe_allow_html=True)

def chart(fig):
    fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#cbd9e9',margin=dict(l=15,r=15,t=45,b=15),colorway=['#31d8c0','#4ca7ed','#a58dff','#f5b757','#fb7185'])
    st.plotly_chart(fig,width='stretch')

if 'token' not in st.session_state:
    st.markdown('<div class="hero"><div class="eyebrow">◈ INTELLIGENCE / CONNECTED</div><h1>Follow the money.<br>Connect the evidence.</h1><p class="muted">Financial Crime Intelligence & Investigation Platform</p></div>',unsafe_allow_html=True)
    l,r=st.columns([1.1,1])
    with l:
        st.subheader('A clearer view of complex networks')
        st.write('Explore transaction relationships, surface explainable investigation leads, and build evidence-grounded briefs with graph-assisted retrieval.')
        st.info('Self-service access • Private workspace per account • Synthetic demonstration data')
        st.caption('Educational and research use. Indicators are leads for review, never proof of criminal activity.')
    with r:
        sign,create=st.tabs(['Sign in','Create account'])
        with sign:
            with st.form('login'):
                username=st.text_input('Username');password=st.text_input('Password',type='password')
                if st.form_submit_button('Sign in →',width='stretch'):
                    try:st.session_state.token=core.login(username,password);st.rerun()
                    except ValueError as e:st.error(str(e))
        with create:
            with st.form('register'):
                un=st.text_input('Choose your username');pw=st.text_input('Choose your password',type='password')
                if st.form_submit_button('Create my workspace →',width='stretch'):
                    try:core.register(un,pw);st.session_state.token=core.login(un,pw);st.rerun()
                    except ValueError as e:st.error(str(e))
    st.stop()
try:u=core.identity(st.session_state.token)
except ValueError:
    st.session_state.clear();st.rerun()
uid=u['id']
with st.sidebar:
    st.markdown('## ◈ FININT')
    st.caption('INVESTIGATION WORKSPACE')
    page=st.radio('Navigate',['Overview','Transactions','Network explorer','GraphRAG engine','Detection center','Knowledge repository','Investigation cases'],label_visibility='collapsed')
    st.divider();st.caption('SIGNED IN AS');st.write(u['username'])
    if st.button('Log out',width='stretch'):
        core.logout(st.session_state.token);st.session_state.clear();st.rerun()
    st.caption('Synthetic data · Illustrative currency units\n\nLocal evidence synthesis · No paid APIs')
@st.fragment(run_every='1s')
def clock():
    now=datetime.now(timezone(timedelta(hours=5,minutes=30)))
    st.caption(f'{now:%A, %d %B %Y}  •  {now:%H:%M:%S} IST  •  {u["username"]}')
clock()
st.title('Financial Crime Intelligence & Investigation Platform')
st.caption('CONNECTED EVIDENCE. EXPLAINABLE LEADS. INFORMED INVESTIGATIONS.')
st.session_state.setdefault('settings',core.DEFAULTS.copy())
df=core.records(uid);findings=core.detect(df,st.session_state.settings);g=core.network(df,findings)
flagged={t for f in findings for t in f['transaction_ids']}
st.markdown(f'### {page}')

if page=='Overview':
    st.markdown('<div class="hero"><div class="eyebrow">YOUR FINANCIAL NETWORK AT A GLANCE</div><h2>Turn connected activity into actionable leads.</h2><span class="muted">Explore relationships and review every finding against its underlying evidence.</span></div>',unsafe_allow_html=True)
    kg=core.knowledge_graph(uid,df,findings)
    metrics=[('Transactions',len(df)),('Accounts',len(g)),('Entities',kg.number_of_nodes()),('Flagged transactions',len(flagged)),('High-risk accounts',sum(a['risk']=='High' for _,a in g.nodes(data=True))),('Investigation cases',len(core.cases(uid))),('Knowledge documents',len(core.documents(uid)))]
    for col,(label,value) in zip(st.columns(7),metrics):col.metric(label,f'{value:,}')
    if df.empty:st.info('Add transactions to start exploring.');st.stop()
    left,right=st.columns([1.5,1])
    d=df.copy();d['day']=pd.to_datetime(d.transaction_date,utc=True).dt.date
    with left:chart(px.area(d.groupby('day',as_index=False).amount.sum(),x='day',y='amount',title='Transaction volume over time'))
    with right:chart(px.pie(names=['Flagged','Unflagged'],values=[len(flagged),len(df)-len(flagged)],hole=.72,title='Transaction review coverage'))
    a,b,c=st.columns(3)
    with a:chart(px.pie(names=[g.nodes[n]['risk'] for n in g],hole=.55,title='Account risk classification'))
    with b:chart(px.histogram(df,x='transaction_type',title='Transaction categories'))
    with c:
        high=[n for n in g if g.nodes[n]['risk']=='High'];q=df[df.sender_account.isin(high)].groupby('sender_account',as_index=False).amount.sum()
        chart(px.bar(q,x='sender_account',y='amount',title='High-risk outgoing activity'))
    st.info(f'Network statistics: {g.number_of_nodes()} accounts · {g.number_of_edges()} transaction edges · {nx.number_weakly_connected_components(g) if g else 0} connected components · density {nx.density(g):.3f}. Entity count includes transactions, synthetic owners, locations, beneficiaries, patterns and documents.')

elif page=='Transactions':
    with st.expander('Import CSV or add a record'):
        st.download_button('Download CSV template / sample',df.head(10).to_csv(index=False),'transactions_sample.csv','text/csv')
        upload=st.file_uploader('CSV with all eight transaction columns',type=['csv'])
        if upload and st.button('Validate and import'):
            try:st.success(f'Imported {core.add_transactions(uid,pd.read_csv(upload).to_dict("records"))} records.');st.rerun()
            except Exception as e:st.error(str(e))
        with st.form('newtransaction'):
            a,b,c=st.columns(3)
            tid=a.text_input('Transaction ID');sender=b.text_input('Sender account');receiver=c.text_input('Receiver account')
            amount=a.number_input('Amount',min_value=.01,value=100.);date=b.date_input('Date');time=c.time_input('Time (UTC)')
            kind=a.selectbox('Type',['Transfer','Wire','Cash','Card']);loc=b.text_input('Location',value='Mumbai');status=c.selectbox('Status',['Completed','Pending','Failed'])
            if st.form_submit_button('Add transaction'):
                try:core.add_transactions(uid,[dict(zip(core.FIELDS,[tid,sender,receiver,amount,datetime.combine(date,time).isoformat(),kind,loc,status]))]);st.rerun()
                except Exception as e:st.error(str(e))
    q=df.copy();a,b,c=st.columns(3)
    search=a.text_input('Search records');account=b.selectbox('Account',['All']+sorted(g));types=c.multiselect('Types',sorted(df.transaction_type.unique()))
    a,b,c=st.columns(3);low=a.number_input('Minimum amount',min_value=0.,value=0.);high=b.number_input('Maximum amount',min_value=0.,value=max(1.,float(df.amount.max()) if len(df) else 1.))
    dates=c.date_input('Date range',value=(pd.to_datetime(df.transaction_date,utc=True).min().date(),pd.to_datetime(df.transaction_date,utc=True).max().date()) if len(df) else (datetime.now().date(),datetime.now().date()))
    if search:q=q[q.astype(str).apply(lambda s:s.str.contains(search,case=False,regex=False)).any(axis=1)]
    if account!='All':q=q[(q.sender_account==account)|(q.receiver_account==account)]
    if types:q=q[q.transaction_type.isin(types)]
    q=q[q.amount.between(low,high)]
    if len(dates)==2:
        days=pd.to_datetime(q.transaction_date,utc=True).dt.date;q=q[(days>=dates[0])&(days<=dates[1])]
    st.caption(f'{len(q):,} matching transactions');st.dataframe(q,width='stretch',hide_index=True)
    st.download_button('Export filtered CSV',q.to_csv(index=False),'filtered_transactions.csv','text/csv')
    with st.expander('Delete a transaction'):
        target=st.selectbox('Transaction to delete',df.transaction_id.tolist() or [''])
        confirm=st.checkbox('Confirm deletion of this record')
        if st.button('Delete record',disabled=not confirm or not target):core.delete_transaction(uid,target);st.rerun()

elif page=='Network explorer':
    a,b,c=st.columns(3);anchor=a.selectbox('Focus account',['All']+sorted(g));risk=b.multiselect('Risk levels',['High','Medium','Low'],default=['High','Medium','Low']);depth=c.slider('Neighborhood hops',1,3,1)
    nodes={n for n in g if g.nodes[n]['risk'] in risk}
    if anchor!='All':nodes &=set(nx.single_source_shortest_path_length(g.to_undirected(),anchor,cutoff=depth))
    sub=g.subgraph(nodes);pos=nx.spring_layout(sub,seed=42)
    fig=go.Figure()
    ex=[];ey=[]
    for s,t in sub.edges():ex.extend([pos[s][0],pos[t][0],None]);ey.extend([pos[s][1],pos[t][1],None])
    fig.add_trace(go.Scatter(x=ex,y=ey,mode='lines',line=dict(color='#41627b',width=1),hoverinfo='skip'))
    colors={'High':'#fb7185','Medium':'#f5b757','Low':'#31d8c0'}
    fig.add_trace(go.Scatter(x=[pos[n][0] for n in sub],y=[pos[n][1] for n in sub],mode='markers+text',text=list(sub),textposition='top center',customdata=[[g.nodes[n]['risk'],g.nodes[n]['risk_score'],g.degree(n)] for n in sub],hovertemplate='%{text}<br>Risk: %{customdata[0]} (%{customdata[1]})<br>Degree: %{customdata[2]}<extra></extra>',marker=dict(size=[15+min(20,g.degree(n)) for n in sub],color=[colors[g.nodes[n]['risk']] for n in sub])))
    fig.update_layout(height=600,xaxis_visible=False,yaxis_visible=False,showlegend=False,title='Account network • hover, zoom and pan');chart(fig)
    st.caption('Teal = Low · Amber = Medium · Rose = High. Lines show connectivity; sender → receiver direction and amounts are in the evidence table below.')
    st.dataframe(df[df.sender_account.isin(nodes)&df.receiver_account.isin(nodes)],hide_index=True,width='stretch')
    a,b=st.columns(2);src=a.selectbox('Path start',sorted(g));dst=b.selectbox('Path end',sorted(g),index=min(1,max(0,len(g)-1)))
    if src and dst:
        try:st.success(' → '.join(nx.shortest_path(g,src,dst)))
        except nx.NetworkXNoPath:st.info('No directed transaction path found.')
    st.write('Most connected accounts');st.dataframe(pd.DataFrame(sorted(g.degree,key=lambda x:-x[1]),columns=['Account','Connections']).head(10),hide_index=True)

elif page=='GraphRAG engine':
    st.write('Account anchors → graph neighborhood and transaction paths → linked detection patterns → TF-IDF passage ranking → cited local investigation brief.')
    query=st.text_area('Investigation question',value='Investigate circular transfers and rapid movement involving ACC-003 and ACC-005.')
    a,b=st.columns(2);account=a.selectbox('Optional anchor',['Automatic']+sorted(g));hops=b.slider('Graph traversal depth',1,3,2)
    if st.button('Generate evidence-grounded brief',type='primary'):
        with st.spinner('Traversing graph and retrieving knowledge…'):st.session_state.result=core.investigate(uid,query,None if account=='Automatic' else account,hops,st.session_state.settings)
    if 'result' in st.session_state:
        result=st.session_state.result;st.markdown(result['summary'])
        st.download_button('Download investigation report',result['summary'],'investigation_report.md','text/markdown')
        st.download_button('Download full evidence JSON',json.dumps(result,indent=2),'investigation_evidence.json','application/json')
        for label,key in [('Graph relationships','relationships'),('Transaction evidence','transactions'),('Retrieved passages','sources')]:
            with st.expander(label):st.dataframe(pd.DataFrame(result[key]),hide_index=True,width='stretch')
        st.caption(f'Knowledge graph: {result["graph_nodes"]} nodes / {result["graph_edges"]} edges. Paths: {result["paths"]}')
        title=st.text_input('Case title',value='Network investigation')
        if st.button('Save as investigation case'):cid=core.save_case(uid,title,result['summary']);st.success(f'Case #{cid} saved.')

elif page=='Detection center':
    st.info('Transparent heuristic scores prioritize human review. They are not probabilities, criminal determinations, or legal reporting thresholds.')
    with st.expander('Configure detection thresholds'):
        with st.form('rules'):
            c1,c2,c3=st.columns(3);cfg={}
            cfg['high_value']=c1.number_input('High-value amount',min_value=1.,value=float(st.session_state.settings['high_value']))
            cfg['split_limit']=c2.number_input('Illustrative split threshold',min_value=1.,value=float(st.session_state.settings['split_limit']))
            cfg['split_count']=c3.number_input('Split count per UTC day',min_value=2,value=int(st.session_state.settings['split_count']))
            cfg['rapid_hours']=c1.number_input('Rapid movement hours',min_value=.1,value=float(st.session_state.settings['rapid_hours']))
            cfg['volume_count']=c2.number_input('Outgoing daily count',min_value=2,value=int(st.session_state.settings['volume_count']))
            cfg['beneficiary_count']=c3.number_input('Distinct daily senders',min_value=2,value=int(st.session_state.settings['beneficiary_count']))
            if st.form_submit_button('Apply rules'):st.session_state.settings=cfg;st.rerun()
    f=pd.DataFrame(findings)
    if f.empty:st.success('No leads under the configured rules.')
    else:
        cat=st.multiselect('Detection categories',sorted(f.category.unique()))
        if cat:f=f[f.category.isin(cat)]
        chart(px.histogram(f,x='category',color='category',title='Investigation leads by rule'))
        st.dataframe(f,hide_index=True,width='stretch');st.download_button('Export detections',f.to_csv(index=False),'detections.csv','text/csv')
        st.caption('Structuring: ≥80% and <100% of split threshold, counted per sender/day. Rapid movement: 80–120% of incoming amount. Circular transfers: directed cycles up to three accounts. Failed and pending transfers do not count as settled flow. Scores: volume 65, high value 70, beneficiary 75, splitting 80, rapid movement 85, cycles 90. Money-laundering indicators are represented by these explainable pattern families.')

elif page=='Knowledge repository':
    st.caption('Seed passages are educational paraphrases with official reference links. They are not quotations or an automatically updated regulatory feed.')
    search=st.text_input('Search knowledge')
    for doc in core.documents(uid):
        if search.lower() not in (doc['title']+' '+doc['content']).lower():continue
        with st.expander(doc['title'],expanded=True):
            st.write(doc['content']);st.write('Reference:',doc['source']);st.caption(f'Document [{doc["id"]}]')
    with st.form('knowledge'):
        title=st.text_input('Document title');content=st.text_area('Document passage');source=st.text_input('Reference URL or provenance',value='User supplied')
        if st.form_submit_button('Add knowledge document'):
            try:core.add_document(uid,title,content,source);st.rerun()
            except ValueError as e:st.error(str(e))

elif page=='Investigation cases':
    cs=core.cases(uid)
    if not cs:st.info('Generate a brief in the GraphRAG engine and save it as a case.')
    for case in cs:
        with st.expander(f'#{case["id"]} · {case["title"]} · {case["status"]}'):
            st.caption(case['created']);st.markdown(case['report'])
            status=st.selectbox('Status',['Open','Reviewing','Closed'],index=['Open','Reviewing','Closed'].index(case['status']),key=f'status{case["id"]}')
            if st.button('Update status',key=f'update{case["id"]}'):core.update_case(uid,case['id'],status);st.rerun()
            st.download_button('Download report',case['report'],f'case_{case["id"]}.md',key=f'download{case["id"]}')
