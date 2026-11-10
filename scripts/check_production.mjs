import {randomBytes} from 'node:crypto';
import {writeFileSync} from 'node:fs';
const base=process.argv[2]||'https://financial-crime-graphrag.vercel.app';
let token;
async function request(path,method='GET',data){
  const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:data===undefined?undefined:JSON.stringify(data)});
  const text=await r.text();
  if(!r.ok)throw Error(`${method} ${path}: ${r.status} ${text.slice(0,150)}`);
  return JSON.parse(text);
}
function check(condition,message){if(!condition)throw Error(message);console.log('PASS',message)}
try{
  const home=await fetch(base);check(home.status===200&&(await home.text()).includes('Follow the money'),'Public dashboard loads without Vercel login');
  check((await request('/health')).status==='ok','Public backend health');
  const credentials={username:'deployment-check-'+randomBytes(8).toString('hex'),password:randomBytes(24).toString('hex')};
  const registration=await request('/auth/register','POST',credentials);
  writeFileSync('data/production-check-user.json',JSON.stringify({id:registration.user_id,username:credentials.username}));
  check(Boolean(registration.user_id),'Open account registration');
  token=(await request('/auth/login','POST',credentials)).access_token;
  check(Boolean(token),'Sign in with chosen credentials');
  check((await request('/transactions')).length===256,'Private synthetic dataset seeded');
  check((await request('/knowledge')).length===4,'Knowledge documents available');
  const brief=await request('/investigate','POST',{query:'Trace ACC-003 and ACC-005',hops:2});
  check(brief.transactions.length>0&&brief.sources.length>0&&brief.relationships.length>0,'GraphRAG retrieves transaction evidence and sources');
  const c=await request('/cases','POST',{title:'Deployment verification',report:brief.summary});
  await request('/cases/'+c.id,'PATCH',{status:'Reviewing'});
  check((await request('/cases')).some(x=>x.id===c.id&&x.status==='Reviewing'),'Investigation cases save and update');
  await request('/auth/logout','POST');
  const revoked=await fetch(base+'/auth/me',{headers:{Authorization:'Bearer '+token}});
  check(revoked.status===401,'Logout revokes session');
  const unauth=await fetch(base+'/transactions');check([401,403].includes(unauth.status),'Private data requires authentication');
}catch(e){console.error(e.message);process.exitCode=1}
