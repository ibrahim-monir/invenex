"""Google Drive + Google Sheets backup for the local SQLite database.

Two independent layers, both optional — if nothing is configured the app runs
exactly as before:

1. **Drive** (`GDRIVE_FOLDER_ID`) — the real safety net. The whole `invenex.db`
   file lives in your own Drive folder. It is downloaded on startup and
   re-uploaded a few seconds after every change, so the database survives the
   host being wiped or shut down. One version per day is pinned in Drive's own
   revision history, so you can also go back to how things were days ago.

2. **Sheets** (`GSHEET_ID`) — a readable mirror. Every table is written to its
   own tab so you can open the spreadsheet and see the data without the app.

The upload never copies the live file directly. It uses SQLite's own backup API
to take a consistent snapshot first, otherwise a copy taken mid-write would be
corrupt.
"""

import atexit
import json
import os
import sqlite3
import tempfile
import threading
from datetime import date, datetime

DB_MIMETYPE = "application/x-sqlite3"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Sheets caps a single cell at 50,000 characters; stay well under it.
MAX_CELL_CHARS = 40000


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def _int_env(name, default):
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_credentials():
    """Service-account credentials from either a JSON blob or a file path."""
    from google.oauth2 import service_account

    raw = _env("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=SCOPES
        )

    path = _env("GOOGLE_SERVICE_ACCOUNT_FILE")
    if path and os.path.exists(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    return None


def _build(service, version, credentials):
    from googleapiclient.discovery import build

    return build(service, version, credentials=credentials, cache_discovery=False)


def _consistent_copy(db_path, target_path):
    """Copy the SQLite file safely, even while the app is writing to it."""
    source = sqlite3.connect(db_path)
    try:
        destination = sqlite3.connect(target_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def _row_count(db_path, table_names):
    """Total rows across the app's tables. Used to spot an empty database."""
    total = 0
    connection = sqlite3.connect(db_path)
    try:
        present = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table in table_names:
            if table in present:
                total += connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.DatabaseError:
        return None  # not a readable database
    finally:
        connection.close()
    return total


class GoogleBackup:
    def __init__(self, db_path):
        self.db_path = db_path
        self.folder_id = _env("GDRIVE_FOLDER_ID")
        self.sheet_id = _env("GSHEET_ID")
        self.db_name = _env("GDRIVE_DB_NAME") or "invenex.db"
        self.debounce = _int_env("BACKUP_DEBOUNCE_SECONDS", 5)
        self.snapshot_keep = _int_env("GDRIVE_SNAPSHOT_KEEP", 14)
        self.sheet_interval = _int_env("SHEET_SYNC_SECONDS", 300)

        self.credentials = None
        self._drive = None
        self._sheets = None
        self._file_id = None

        self._dirty = threading.Event()
        self._lock = threading.Lock()
        self._worker = None
        self._stopping = threading.Event()
        self._last_sheet_sync = 0.0
        self._models = []

        self.last_error = None
        self.last_upload_at = None

    # ---- availability ---------------------------------------------------

    @property
    def enabled(self):
        return bool(self.credentials) and bool(self.folder_id or self.sheet_id)

    @property
    def drive_enabled(self):
        return bool(self.credentials) and bool(self.folder_id)

    @property
    def sheets_enabled(self):
        return bool(self.credentials) and bool(self.sheet_id)

    def connect(self):
        """Load credentials. Returns True if any backup target is configured."""
        try:
            self.credentials = _load_credentials()
        except Exception as exc:  # bad JSON, wrong key file, ...
            self.last_error = f"credentials: {exc}"
            self.credentials = None
        return self.enabled

    @property
    def drive(self):
        if self._drive is None:
            self._drive = _build("drive", "v3", self.credentials)
        return self._drive

    @property
    def sheets(self):
        if self._sheets is None:
            self._sheets = _build("sheets", "v4", self.credentials)
        return self._sheets

    # ---- drive: locating the remote file --------------------------------

    def _find_remote_db(self):
        if self._file_id:
            return self._file_id
        query = (
            f"name = '{self.db_name}' and '{self.folder_id}' in parents and trashed = false"
        )
        result = (
            self.drive.files()
            .list(q=query, fields="files(id, name, modifiedTime)", pageSize=1)
            .execute()
        )
        files = result.get("files", [])
        self._file_id = files[0]["id"] if files else None
        return self._file_id

    # ---- drive: restore -------------------------------------------------

    def restore(self):
        """Pull the database down from Drive. Called before the app opens it.

        Only restores when there is no usable local database, so a running
        instance never has its live data replaced underneath it.
        """
        if not self.drive_enabled:
            return False

        from googleapiclient.http import MediaIoBaseDownload

        try:
            file_id = self._find_remote_db()
            if not file_id:
                return False

            local_exists = os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0
            if local_exists:
                return False

            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            temp_path = self.db_path + ".download"
            request = self.drive.files().get_media(fileId=file_id)
            with open(temp_path, "wb") as handle:
                downloader = MediaIoBaseDownload(handle, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            # Make sure what we downloaded is actually a readable database
            # before it replaces anything on disk.
            check = sqlite3.connect(temp_path)
            try:
                check.execute("PRAGMA schema_version").fetchone()
            finally:
                check.close()

            os.replace(temp_path, self.db_path)
            return True
        except Exception as exc:
            self.last_error = f"restore: {exc}"
            return False

    def force_restore(self):
        """Overwrite the local database with the Drive copy (manual recovery)."""
        if not self.drive_enabled:
            raise RuntimeError("Drive backup is not configured.")
        if os.path.exists(self.db_path):
            os.replace(self.db_path, self.db_path + ".replaced")
        return self.restore()

    # ---- drive: upload --------------------------------------------------

    def _upload(self, allow_empty=False):
        """Overwrite the Drive copy with the current database.

        A service account has no storage of its own, so it can only *update* a
        file that already exists and is owned by you — it cannot create one.
        The file is placed in the folder once, by hand; everything after that
        is an update, and the bytes count against your own Drive quota.
        """
        from googleapiclient.http import MediaFileUpload

        file_id = self._find_remote_db()
        if not file_id:
            raise RuntimeError(
                f"'{self.db_name}' is not in the Drive folder yet. Upload any "
                f"small file with that exact name into the folder once, then "
                f"run this again — from then on it updates itself."
            )

        handle, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            _consistent_copy(self.db_path, temp_path)

            if not allow_empty and not self._safe_to_overwrite(temp_path, file_id):
                self.last_error = (
                    "refused to upload: this database is empty but the Drive "
                    "copy has data. Restore first, or use `restore_backup.py "
                    "push` if wiping the backup is really what you want."
                )
                print(f"[backup] {self.last_error}")
                return

            media = MediaFileUpload(temp_path, mimetype=DB_MIMETYPE, resumable=False)
            self.drive.files().update(fileId=file_id, media_body=media).execute()
            self.last_upload_at = datetime.now()
            self._pin_daily_revision(file_id)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def _safe_to_overwrite(self, local_copy, file_id):
        """Never let a blank database wipe out a good backup.

        This is the accident worth guarding: the app boots somewhere with no
        data — a fresh host, credentials added after the first run — creates an
        empty database, and the uploader faithfully copies that emptiness over
        the only surviving copy. If the local side has no rows, check what is
        in Drive before overwriting it.
        """
        tables = [model.__tablename__ for model in self._models]
        if not tables:
            return True  # nothing registered yet, cannot judge

        local_rows = _row_count(local_copy, tables)
        if local_rows is None or local_rows > 0:
            return True

        from googleapiclient.http import MediaIoBaseDownload

        handle, remote_copy = tempfile.mkstemp(suffix=".remote.db")
        os.close(handle)
        try:
            request = self.drive.files().get_media(fileId=file_id)
            with open(remote_copy, "wb") as sink:
                downloader = MediaIoBaseDownload(sink, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            remote_rows = _row_count(remote_copy, tables)
            # None = the remote is not a database yet (the placeholder file).
            return not remote_rows
        except Exception:
            return False  # cannot verify, so do not risk it
        finally:
            try:
                os.remove(remote_copy)
            except OSError:
                pass

    def _revisions(self, file_id):
        result = (
            self.drive.revisions()
            .list(
                fileId=file_id,
                fields="revisions(id, modifiedTime, keepForever)",
                pageSize=1000,
            )
            .execute()
        )
        return result.get("revisions", [])

    def _pin_daily_revision(self, file_id):
        """Keep one restorable version per day.

        Drive already versions every update, but it drops old revisions on its
        own. Pinning (`keepForever`) makes today's version stick around, which
        gives the same protection as dated copies without creating any files.
        """
        if self.snapshot_keep <= 0:
            return
        try:
            revisions = self._revisions(file_id)
            if not revisions:
                return

            pinned = [r for r in revisions if r.get("keepForever")]
            today = date.today().isoformat()
            if any(r.get("modifiedTime", "").startswith(today) for r in pinned):
                return  # today is already covered

            newest = revisions[-1]
            self.drive.revisions().update(
                fileId=file_id,
                revisionId=newest["id"],
                body={"keepForever": True},
            ).execute()

            # Unpin the oldest ones once we are past the limit.
            pinned.append(newest)
            for stale in pinned[: max(0, len(pinned) - self.snapshot_keep)]:
                try:
                    self.drive.revisions().update(
                        fileId=file_id,
                        revisionId=stale["id"],
                        body={"keepForever": False},
                    ).execute()
                except Exception:
                    pass  # an extra pinned revision is harmless
        except Exception as exc:
            self.last_error = f"snapshot: {exc}"

    # ---- sheets mirror --------------------------------------------------

    def register_models(self, models):
        self._models = list(models)

    def _sheet_rows(self, model, session):
        columns = [column.name for column in model.__table__.columns]
        rows = [columns]
        for record in session.query(model).all():
            row = []
            for column in columns:
                value = getattr(record, column, None)
                if value is None:
                    row.append("")
                elif isinstance(value, (datetime, date)):
                    row.append(value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat())
                elif isinstance(value, (int, float)):
                    row.append(value)
                else:
                    row.append(str(value)[:MAX_CELL_CHARS])
            rows.append(row)
        return rows

    def _ensure_tabs(self, wanted):
        meta = self.sheets.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        present = {s["properties"]["title"] for s in meta.get("sheets", [])}
        missing = [title for title in wanted if title not in present]
        if not missing:
            return
        self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": title}}} for title in missing
                ]
            },
        ).execute()

    def sync_sheets(self, session):
        """Write every table to its own tab. One batch call for all of them."""
        if not self.sheets_enabled or not self._models:
            return False

        payload = {}
        for model in self._models:
            payload[model.__tablename__] = self._sheet_rows(model, session)

        self._ensure_tabs(payload.keys())

        self.sheets.spreadsheets().values().batchClear(
            spreadsheetId=self.sheet_id,
            body={"ranges": list(payload.keys())},
        ).execute()

        self.sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"{title}!A1", "values": rows}
                    for title, rows in payload.items()
                ],
            },
        ).execute()
        return True

    # ---- background worker ----------------------------------------------

    def mark_dirty(self):
        self._dirty.set()

    def start_worker(self, session_factory):
        if not self.enabled or self._worker is not None:
            return

        def run():
            while not self._stopping.is_set():
                # Wake on a change, but also tick regularly so the Sheets
                # mirror still refreshes on its own schedule.
                self._dirty.wait(timeout=self.sheet_interval)
                if self._stopping.is_set():
                    break
                if not self._dirty.is_set():
                    continue
                # Let a burst of writes settle into a single upload.
                self._stopping.wait(self.debounce)
                self._dirty.clear()
                self.flush(session_factory)

        self._worker = threading.Thread(target=run, name="google-backup", daemon=True)
        self._worker.start()
        atexit.register(self.shutdown, session_factory)

    def flush(self, session_factory=None):
        """Push the database to Drive, and the tables to Sheets if it is due."""
        import time

        with self._lock:
            if self.drive_enabled:
                try:
                    self._upload()
                except Exception as exc:
                    self.last_error = f"upload: {exc}"

            if self.sheets_enabled and session_factory is not None:
                due = (time.monotonic() - self._last_sheet_sync) >= self.sheet_interval
                if due:
                    session = session_factory()
                    try:
                        self.sync_sheets(session)
                        self._last_sheet_sync = time.monotonic()
                    except Exception as exc:
                        self.last_error = f"sheets: {exc}"
                    finally:
                        session.close()

    def shutdown(self, session_factory=None):
        """Final upload on exit so the last few writes are never lost."""
        if self._dirty.is_set() and self.drive_enabled:
            self._dirty.clear()
            with self._lock:
                try:
                    self._upload()
                except Exception as exc:
                    self.last_error = f"shutdown upload: {exc}"
        self._stopping.set()


def _install_shutdown_handler(db_session):
    """Flush to Drive when the host stops us.

    Render (and most hosts) send SIGTERM before shutting a container down.
    Python's atexit does not run for a signal, so without this the last few
    seconds of writes would never reach Drive.
    """
    import signal

    def handler(signum, frame):
        try:
            backup.shutdown(db_session)
        finally:
            if callable(previous.get(signum)):
                previous[signum](signum, frame)
            else:
                raise SystemExit(0)

    previous = {}
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass  # not the main thread — atexit still covers a clean exit


# ---- module-level wiring used by app.py ---------------------------------

backup = None


def init(db_path):
    """Create the backup handler and restore from Drive if the disk is empty.

    Must run *before* the app opens the database.
    """
    global backup
    backup = GoogleBackup(db_path)
    if not backup.connect():
        return backup
    restored = backup.restore()
    if restored:
        print(f"[backup] restored {db_path} from Google Drive")
    return backup


def start(db_session, models):
    """Hook into commits and start the uploader. Runs after db.create_all()."""
    if backup is None or not backup.enabled:
        return

    from sqlalchemy import event

    backup.register_models(models)

    @event.listens_for(db_session, "after_commit")
    def _on_commit(session):  # noqa: ARG001 - signature fixed by SQLAlchemy
        backup.mark_dirty()

    backup.start_worker(db_session)
    _install_shutdown_handler(db_session)

    targets = []
    if backup.drive_enabled:
        targets.append("Drive")
    if backup.sheets_enabled:
        targets.append("Sheets")
    print(f"[backup] enabled -> {' + '.join(targets)}")
