"""Build a minimal deployable package, excluding local data, tests and Streamlit."""
from pathlib import Path
import shutil
import json
root=Path(__file__).resolve().parents[1]
out=root/'deploy-output'
out.mkdir(exist_ok=True)
for name in ['api.py','core.py']:
    shutil.copy2(root/name,out/name)
(out/'web').mkdir(exist_ok=True)
shutil.copy2(root/'web'/'index.html',out/'web'/'index.html')
(out/'index.py').write_text('from api import app\n',encoding='utf-8')
(out/'requirements.txt').write_text('fastapi>=0.115,<1\nSQLAlchemy>=2.0,<3\npsycopg[binary]>=3.2,<4\npandas>=2.2,<3\nnumpy>=2,<3\nnetworkx>=3.4,<4\n',encoding='utf-8')
dependencies=(out/'requirements.txt').read_text().splitlines()
(out/'pyproject.toml').write_text('[project]\nname = "financial-crime-graphrag"\nversion = "1.0.0"\nrequires-python = ">=3.12,<3.13"\ndependencies = '+json.dumps(dependencies)+'\n',encoding='utf-8')
(out/'.vercelignore').write_text('.env\n.env.*\n__pycache__\n*.pyc\ndata\n',encoding='utf-8')
(out/'vercel.json').write_text('{"$schema":"https://openapi.vercel.sh/vercel.json","framework":"fastapi","functions":{"index.py":{"maxDuration":60}},"headers":[{"source":"/(.*)","headers":[{"key":"X-Content-Type-Options","value":"nosniff"},{"key":"Referrer-Policy","value":"strict-origin-when-cross-origin"}]}]}\n',encoding='utf-8')
print('Prepared deploy-output: web dashboard + FastAPI + persistent database support. No local database or credentials included.')
