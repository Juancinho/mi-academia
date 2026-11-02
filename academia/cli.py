"""Herramientas sin interfaz para importar, exportar y restaurar."""
import argparse
import sqlite3
from pathlib import Path

from .db import backup_bytes, default_path, full_export, restore_backup
from .models import ImportBundle, parse_bundle
from .service import Academy


def main():
    parser = argparse.ArgumentParser(description="Mi Academia · datos locales")
    parser.add_argument("--db", type=Path, default=default_path(), help="Ruta SQLite (antes del subcomando)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Inicializar base vacía")
    imp = sub.add_parser("import", help="Validar e importar sesiones JSON")
    imp.add_argument("file", type=Path)
    imp.add_argument("--dry-run", action="store_true")
    for name in ("backup", "export", "export-sessions", "schema"):
        cmd = sub.add_parser(name)
        cmd.add_argument("output", type=Path)
    restore = sub.add_parser("restore", help="Restaurar copia SQLite en --db; el destino debe ser nuevo")
    restore.add_argument("file", type=Path)
    sub.add_parser("stats")
    args = parser.parse_args()
    try:
        if args.command == "restore":
            restore_backup(args.file, args.db)
            print(f"Copia restaurada en {args.db.resolve()}")
            return
        if args.command == "schema":
            import json
            args.output.write_text(json.dumps(ImportBundle.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Contrato guardado en {args.output.resolve()}")
            return
        academy = Academy(args.db)
        if args.command == "init":
            print(f"Base preparada: {args.db.resolve()}")
        elif args.command == "import":
            bundle = parse_bundle(args.file.read_bytes())
            print(academy.preview_import(bundle) if args.dry_run else academy.import_bundle(bundle))
        elif args.command == "backup":
            with args.output.open("xb") as output:
                output.write(backup_bytes(args.db))
            print(f"Copia guardada en {args.output.resolve()}")
        elif args.command in ("export", "export-sessions"):
            content = full_export(args.db) if args.command == "export" else academy.export_sessions()
            with args.output.open("x", encoding="utf-8") as output:
                output.write(content)
            print(f"Exportación guardada en {args.output.resolve()}")
        elif args.command == "stats":
            import json
            print(json.dumps(academy.statistics(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
