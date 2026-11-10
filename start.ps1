param([switch]$Api)
$projectPath = $PSScriptRoot
Set-Location -LiteralPath $projectPath
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { python -m venv .venv }
if ($Api) { & $pythonPath -m uvicorn api:app --host 127.0.0.1 --port 8010 }
else { & $pythonPath -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 }
