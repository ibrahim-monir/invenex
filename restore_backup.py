"""Backup and recovery commands for the Google Drive / Sheets copies.

    python restore_backup.py status        what is configured, and is it working
    python restore_backup.py push          upload the database to Drive right now
    python restore_backup.py sheets        refresh the Google Sheet right now
    python restore_backup.py list          show the snapshots kept in Drive
    python restore_backup.py pull          replace the local database with Drive's
    python restore_backup.py from-sheets   rebuild the database from the Sheet

`pull` and `from-sheets` overwrite local data, so both ask for confirmation.
The previous database is kept as `data/invenex.db.replaced` either way.
"""

import sys
from datetime import date, datetime

import google_backup
from app import BACKUP_MODELS, app, db


def _backup():
    handler = google_backup.backup
    if handler is None or not handler.enabled:
        print("Google backup is not configured.")
        print("Set GOOGLE_SERVICE_ACCOUNT_FILE (or ..._JSON) plus GDRIVE_FOLDER_ID")
        print("and/or GSHEET_ID in your .env — see GOOGLE_BACKUP_SETUP.md")
        sys.exit(1)
    return handler


def _confirm(message):
    answer = input(f"{message} [yes/no]: ").strip().lower()
    if answer not in {"yes", "y"}:
        print("Cancelled.")
        sys.exit(0)


def cmd_status():
    handler = google_backup.backup
    if handler is None:
        print("Backup handler not created (app is using Postgres, not SQLite).")
        return

    print(f"credentials : {'loaded' if handler.credentials else 'MISSING'}")
    print(f"drive       : {'on -> folder ' + handler.folder_id if handler.drive_enabled else 'off'}")
    print(f"sheets      : {'on -> sheet ' + handler.sheet_id if handler.sheets_enabled else 'off'}")
    print(f"db file     : {handler.db_path}")
    print(f"snapshots   : keep {handler.snapshot_keep} daily copies")
    if handler.last_error:
        print(f"last error  : {handler.last_error}")

    if handler.drive_enabled:
        remote = handler._find_remote_db()
        print(f"remote db   : {'found (' + remote + ')' if remote else 'not uploaded yet'}")


def cmd_push():
    handler = _backup()
    handler._upload()
    print(f"Uploaded {handler.db_path} to Google Drive.")


def cmd_sheets():
    handler = _backup()
    if not handler.sheets_enabled:
        print("GSHEET_ID is not set — nothing to sync.")
        sys.exit(1)
    handler.register_models(BACKUP_MODELS)
    with app.app_context():
        handler.sync_sheets(db.session)
    print("Google Sheet updated.")


def cmd_list():
    handler = _backup()
    if not handler.drive_enabled:
        print("GDRIVE_FOLDER_ID is not set.")
        sys.exit(1)
    result = (
        handler.drive.files()
        .list(
            q=f"'{handler.folder_id}' in parents and trashed = false",
            fields="files(id, name, size, modifiedTime)",
            orderBy="name desc",
            pageSize=100,
        )
        .execute()
    )
    files = result.get("files", [])
    if not files:
        print("Drive folder is empty.")
        return
    for entry in files:
        size = int(entry.get("size", 0))
        print(f"{entry['name']:32} {size:>10,} bytes   {entry.get('modifiedTime', '')}")


def cmd_pull():
    handler = _backup()
    if not handler.drive_enabled:
        print("GDRIVE_FOLDER_ID is not set.")
        sys.exit(1)
    _confirm("This replaces your local database with the copy from Drive. Continue?")
    if handler.force_restore():
        print(f"Restored {handler.db_path} from Drive.")
        print(f"Previous file kept as {handler.db_path}.replaced")
    else:
        print("Nothing restored — no database found in the Drive folder.")


def _coerce(column, raw):
    """Turn a spreadsheet cell back into the type the column expects."""
    if raw is None or raw == "":
        return None
    kind = column.type.__class__.__name__
    text = str(raw).strip()
    try:
        if kind == "Integer":
            return int(float(text))
        if kind == "Float":
            return float(text)
        if kind == "Boolean":
            return text.lower() in {"true", "1", "yes"}
        if kind == "Date":
            return date.fromisoformat(text[:10])
        if kind == "DateTime":
            return datetime.fromisoformat(text)
    except ValueError:
        return None
    return text


def cmd_from_sheets():
    handler = _backup()
    if not handler.sheets_enabled:
        print("GSHEET_ID is not set.")
        sys.exit(1)
    _confirm("This wipes the local database and rebuilds it from the Sheet. Continue?")

    values = handler.sheets.spreadsheets().values()

    with app.app_context():
        # Children first so foreign keys never point at a row that is gone.
        for model in reversed(BACKUP_MODELS):
            db.session.query(model).delete()
        db.session.commit()

        for model in BACKUP_MODELS:
            table = model.__tablename__
            try:
                data = values.get(
                    spreadsheetId=handler.sheet_id, range=table
                ).execute()
            except Exception as exc:
                print(f"{table:16} skipped ({exc})")
                continue

            rows = data.get("values", [])
            if len(rows) < 2:
                print(f"{table:16} 0 rows")
                continue

            header = rows[0]
            columns = {c.name: c for c in model.__table__.columns}
            added = 0
            for row in rows[1:]:
                if not any(str(cell).strip() for cell in row):
                    continue
                payload = {}
                for index, name in enumerate(header):
                    column = columns.get(name)
                    if column is None:
                        continue
                    cell = row[index] if index < len(row) else None
                    payload[name] = _coerce(column, cell)
                db.session.add(model(**payload))
                added += 1
            db.session.commit()
            print(f"{table:16} {added} rows")

        # No sequence fixup needed: these tables use SQLite's implicit rowid,
        # so the next insert picks up at max(id) + 1 on its own.

    print("Rebuilt the database from the Google Sheet.")
    if handler.drive_enabled:
        handler._upload()
        print("Uploaded the rebuilt database back to Drive.")


COMMANDS = {
    "status": cmd_status,
    "push": cmd_push,
    "sheets": cmd_sheets,
    "list": cmd_list,
    "pull": cmd_pull,
    "from-sheets": cmd_from_sheets,
}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[command]()
