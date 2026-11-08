"""Install the authorized per-user Obsidian sync without changing execution policy."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from academia.vault_sync import atomic_write
from academia.windows_secret import transform


def quote_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt" or not args.vault.is_dir():
        raise SystemExit("Se necesita Windows y un vault existente.")
    project = Path(__file__).resolve().parent.parent
    configuration = project / ".vault-sync"
    configuration.mkdir(exist_ok=True)
    print("Ready for private service credential on stdin (not echoed).", flush=True)
    token = sys.stdin.readline().strip()
    if not token:
        raise SystemExit("Falta la credencial privada de Sites.")
    protected = transform(token.encode("utf-8"))
    (configuration / "credential.dpapi").write_bytes(protected)
    token = None
    config_path = configuration / "config.json"
    atomic_write(config_path, json.dumps({"vault": str(args.vault.resolve()), "url": "https://mi-academia-juancinho.juan-el-g.chatgpt.site/api/vault-sync"}, ensure_ascii=False, indent=2))
    runner = Path(sys.executable).with_name("pythonw.exe")
    arguments = '-m academia.vault_sync --config "' + str(config_path) + '"'
    command = "\n".join([
        "$ErrorActionPreference='Stop'",
        "$syncUser=[Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$syncAction=New-ScheduledTaskAction -Execute " + quote_ps(str(runner)) + " -Argument " + quote_ps(arguments) + " -WorkingDirectory " + quote_ps(str(project)),
        "$syncLogon=New-ScheduledTaskTrigger -AtLogOn -User $syncUser",
        "$syncRepeat=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval ([TimeSpan]::FromMinutes(15))",
        "$syncSettings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::FromMinutes(5))",
        "$syncPrincipal=New-ScheduledTaskPrincipal -UserId $syncUser -LogonType Interactive -RunLevel Limited",
        "Register-ScheduledTask -TaskName 'Mi Academia - Obsidian' -Action $syncAction -Trigger @($syncLogon,$syncRepeat) -Settings $syncSettings -Principal $syncPrincipal -Description 'Sincroniza cuadernos de Mi Academia sin sobrescribir notas personales.' -Force | Select-Object TaskName,State | ConvertTo-Json -Compress",
    ])
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        print(json.dumps({"configured": True, "scheduled": False, "error": "No se pudo registrar la tarea de Windows."}))
        raise SystemExit(1)
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
