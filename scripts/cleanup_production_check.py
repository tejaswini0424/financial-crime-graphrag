"""Remove only the temporary account created by check_production.mjs."""
from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
proof=json.loads((root/'data/production-check-user.json').read_text())
if not proof['username'].startswith('deployment-check-'):
    raise RuntimeError('Refusing to remove an account that is not a deployment verification account.')
for line in (root/'deploy-output/.env.production.local').read_text(encoding='utf-8-sig').splitlines():
    if line.startswith('DATABASE_URL='):
        value=line.split('=',1)[1]
        os.environ['DATABASE_URL']=json.loads(value) if value.startswith('"') else value
        break
else:raise RuntimeError('No production database connection configured.')
import core
with core.Session() as s:
    user=s.query(core.User).filter_by(id=proof['id'],username=proof['username']).first()
    if user:
        for cls in [core.Transaction,core.Document,core.Case,core.Login]:
            s.query(cls).filter_by(user=user.id).delete()
        s.delete(user);s.commit()
print('Removed the temporary deployment verification account and its synthetic data.')
