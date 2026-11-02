$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonAcademia = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonAcademia)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno. Instala Python 3.11 o superior.' }
}
& $pythonAcademia -c 'import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(name) is not None for name in ("streamlit", "fsrs", "pydantic", "academia")) else 1)'
if ($LASTEXITCODE -ne 0) {
    & $pythonAcademia -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias. Comprueba la conexión.' }
}
& $pythonAcademia -m streamlit run app.py --server.address 127.0.0.1
