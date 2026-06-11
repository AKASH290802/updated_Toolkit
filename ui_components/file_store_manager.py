"""
file_store_manager.py
SQLite-backed file registry for DM Toolkit.
- Source files are physically copied into file_store/source/ for persistence.
- Output files are registered in-place (not copied) since they live in their
  own directories (Validation/, genai_validation_results/, etc.)
"""

import sqlite3
import os
import shutil
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'dm_toolkit_files.db')
SOURCE_STORE = os.path.join(PROJECT_ROOT, 'file_store', 'source')
OUTPUT_STORE = os.path.join(PROJECT_ROOT, 'file_store', 'output')


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create tables and storage directories if they do not exist."""
    os.makedirs(SOURCE_STORE, exist_ok=True)
    os.makedirs(OUTPUT_STORE, exist_ok=True)
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT    NOT NULL,
                stored_path   TEXT    NOT NULL UNIQUE,
                org_name      TEXT    DEFAULT 'unknown',
                object_name   TEXT    DEFAULT '',
                file_size     INTEGER DEFAULT 0,
                row_count     INTEGER DEFAULT 0,
                col_count     INTEGER DEFAULT 0,
                file_type     TEXT    DEFAULT '',
                uploaded_at   TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS output_files (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name  TEXT    NOT NULL,
                stored_path    TEXT    NOT NULL UNIQUE,
                org_name       TEXT    DEFAULT 'unknown',
                object_name    TEXT    DEFAULT '',
                operation_type TEXT    DEFAULT '',
                file_size      INTEGER DEFAULT 0,
                row_count      INTEGER DEFAULT 0,
                status         TEXT    DEFAULT '',
                source_file_id INTEGER,
                generated_at   TEXT    NOT NULL,
                FOREIGN KEY (source_file_id) REFERENCES source_files(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name   TEXT    NOT NULL,
                direction       TEXT    NOT NULL,
                source_label    TEXT    DEFAULT '',
                target_label    TEXT    DEFAULT '',
                object_name     TEXT    DEFAULT '',
                table_name      TEXT    DEFAULT '',
                operation       TEXT    DEFAULT '',
                status          TEXT    DEFAULT 'pending',
                records_success INTEGER DEFAULT 0,
                records_failed  INTEGER DEFAULT 0,
                error_message   TEXT    DEFAULT '',
                config_json     TEXT    DEFAULT '{}',
                started_at      TEXT    NOT NULL,
                finished_at     TEXT    DEFAULT ''
            )
        """)
        conn.commit()


def register_source_file(source, original_name, org_name='unknown', object_name='',
                          row_count=0, col_count=0):
    """
    Save a source file to file_store/source/ and register it in SQLite.

    Parameters
    ----------
    source : Streamlit UploadedFile, bytes/bytearray, or str (file path)
    original_name : str  — display name (e.g. uploaded_file.name)
    org_name, object_name : str — metadata labels
    row_count, col_count  : int — optional DataFrame dimensions

    Returns
    -------
    int  file_id on success, or None on failure
    """
    initialize_db()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    org_slug = (org_name or 'unknown').replace(' ', '_')
    obj_slug = (object_name or 'general').replace(' ', '_')
    org_dir = os.path.join(SOURCE_STORE, org_slug, obj_slug)
    os.makedirs(org_dir, exist_ok=True)

    stored_name = f"{ts}_{original_name}"
    stored_path = os.path.join(org_dir, stored_name)

    try:
        # Write the file bytes to disk
        if hasattr(source, 'getbuffer'):
            # Streamlit UploadedFile
            with open(stored_path, 'wb') as f:
                f.write(source.getbuffer())
        elif isinstance(source, (bytes, bytearray)):
            with open(stored_path, 'wb') as f:
                f.write(source)
        elif isinstance(source, str) and os.path.exists(source):
            shutil.copy2(source, stored_path)
        else:
            return None

        file_size = os.path.getsize(stored_path)
        file_type = os.path.splitext(original_name)[1].lower()
        uploaded_at = datetime.now().isoformat()

        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO source_files
                   (original_name, stored_path, org_name, object_name,
                    file_size, row_count, col_count, file_type, uploaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (original_name, stored_path, org_name or 'unknown',
                 object_name or '', file_size, row_count, col_count,
                 file_type, uploaded_at)
            )
            conn.commit()
            return cursor.lastrowid

    except Exception:
        return None


def register_output_file(file_path, original_name=None, org_name='unknown',
                          object_name='', operation_type='', row_count=0,
                          status='', source_file_id=None):
    """
    Register a generated output file (stays in its current location).

    Parameters
    ----------
    file_path      : str — absolute path to the file on disk
    original_name  : str — display name (defaults to basename)
    org_name, object_name, operation_type : str — metadata labels
    row_count      : int — optional record count
    status         : str — e.g. 'pass', 'fail', 'mixed'
    source_file_id : int — FK to source_files if known

    Returns
    -------
    int  file_id on success, or None on failure
    """
    initialize_db()

    if not file_path or not os.path.exists(file_path):
        return None

    try:
        file_size = os.path.getsize(file_path)
        name = original_name or os.path.basename(file_path)
        generated_at = datetime.now().isoformat()

        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO output_files
                   (original_name, stored_path, org_name, object_name,
                    operation_type, file_size, row_count, status,
                    source_file_id, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, file_path, org_name or 'unknown', object_name or '',
                 operation_type or '', file_size, row_count, status or '',
                 source_file_id, generated_at)
            )
            conn.commit()
            return cursor.lastrowid

    except Exception:
        return None


def list_source_files(org_name=None, object_name=None, limit=300):
    """Return list of source file dicts, newest first."""
    initialize_db()
    query = "SELECT * FROM source_files WHERE 1=1"
    params = []
    if org_name:
        query += " AND org_name = ?"
        params.append(org_name)
    if object_name:
        query += " AND object_name = ?"
        params.append(object_name)
    query += " ORDER BY uploaded_at DESC LIMIT ?"
    params.append(limit)

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_output_files(org_name=None, object_name=None, operation_type=None, limit=300):
    """Return list of output file dicts, newest first."""
    initialize_db()
    query = "SELECT * FROM output_files WHERE 1=1"
    params = []
    if org_name:
        query += " AND org_name = ?"
        params.append(org_name)
    if object_name:
        query += " AND object_name = ?"
        params.append(object_name)
    if operation_type:
        query += " AND operation_type = ?"
        params.append(operation_type)
    query += " ORDER BY generated_at DESC LIMIT ?"
    params.append(limit)

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_source_file(file_id):
    """Delete a source file record and its stored copy on disk."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT stored_path FROM source_files WHERE id = ?", (file_id,)
        ).fetchone()
        if row:
            try:
                if os.path.exists(row['stored_path']):
                    os.remove(row['stored_path'])
            except Exception:
                pass
            conn.execute("DELETE FROM source_files WHERE id = ?", (file_id,))
            conn.commit()
            return True
    return False


def delete_output_file(file_id):
    """Delete an output file record and the file on disk."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT stored_path FROM output_files WHERE id = ?", (file_id,)
        ).fetchone()
        if row:
            try:
                if os.path.exists(row['stored_path']):
                    os.remove(row['stored_path'])
            except Exception:
                pass
            conn.execute("DELETE FROM output_files WHERE id = ?", (file_id,))
            conn.commit()
            return True
    return False


def get_file_stats():
    """Return summary statistics for display in the File Library header."""
    initialize_db()
    with _get_connection() as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        output_count = conn.execute("SELECT COUNT(*) FROM output_files").fetchone()[0]
        source_size  = conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM source_files").fetchone()[0]
        output_size  = conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM output_files").fetchone()[0]
        org_rows     = conn.execute("SELECT COUNT(DISTINCT org_name) FROM source_files").fetchone()[0]
    return {
        'source_count':   source_count,
        'output_count':   output_count,
        'source_size_mb': round(source_size  / (1024 * 1024), 2),
        'output_size_mb': round(output_size  / (1024 * 1024), 2),
        'org_count':      org_rows,
    }


def scan_and_register_existing():
    """
    Scan known output/source directories and register files not yet tracked.
    Safe to call on every startup — duplicate paths are ignored by UNIQUE constraint.
    Returns the count of newly registered files.
    """
    initialize_db()
    registered = 0

    # --- Output directories ---
    output_dirs = {
        'genai_validation_results': 'GenAI Validation',
        'Validation':               'Validation',
        'mapping_logs':             'Mapping',
        'DataLoader_Logs':          'Data Load',
    }

    for rel_dir, op_type in output_dirs.items():
        abs_dir = os.path.join(PROJECT_ROOT, rel_dir)
        if not os.path.exists(abs_dir):
            continue
        for root, dirs, files in os.walk(abs_dir):
            for fname in files:
                if fname.startswith('~$'):
                    continue
                if not fname.endswith(('.csv', '.xlsx', '.xls', '.json', '.psv')):
                    continue
                fpath = os.path.join(root, fname)
                with _get_connection() as conn:
                    exists = conn.execute(
                        "SELECT 1 FROM output_files WHERE stored_path = ?", (fpath,)
                    ).fetchone()
                    if not exists:
                        # Try to infer object name from filename prefix
                        obj = fname.split('_')[0] if '_' in fname else ''
                        conn.execute(
                            """INSERT INTO output_files
                               (original_name, stored_path, org_name, object_name,
                                operation_type, file_size, row_count, status, generated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (fname, fpath, 'unknown', obj, op_type,
                             os.path.getsize(fpath), 0, 'existing',
                             datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat())
                        )
                        conn.commit()
                        registered += 1

    # --- Source files already in DataFiles/ ---
    datafiles_dir = os.path.join(PROJECT_ROOT, 'DataFiles')
    if os.path.exists(datafiles_dir):
        for root, dirs, files in os.walk(datafiles_dir):
            for fname in files:
                if fname.startswith('~$'):
                    continue
                if not fname.endswith(('.csv', '.xlsx', '.xls', '.psv')):
                    continue
                fpath = os.path.join(root, fname)
                with _get_connection() as conn:
                    exists = conn.execute(
                        "SELECT 1 FROM source_files WHERE stored_path = ?", (fpath,)
                    ).fetchone()
                    if not exists:
                        rel = os.path.relpath(fpath, datafiles_dir)
                        parts = rel.replace('\\', '/').split('/')
                        org = parts[0] if len(parts) > 0 else 'unknown'
                        obj = parts[1] if len(parts) > 1 else ''
                        conn.execute(
                            """INSERT INTO source_files
                               (original_name, stored_path, org_name, object_name,
                                file_size, row_count, col_count, file_type, uploaded_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (fname, fpath, org, obj, os.path.getsize(fpath),
                             0, 0, os.path.splitext(fname)[1].lower(),
                             datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat())
                        )
                        conn.commit()
                        registered += 1

    return registered


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline run persistence
# ─────────────────────────────────────────────────────────────────────────────

def save_pipeline_run(pipeline_name, direction, source_label, target_label,
                      object_name, table_name, operation, status,
                      records_success, records_failed, error_message, config_dict,
                      started_at, finished_at=''):
    """Persist a pipeline run record. Returns the new run id."""
    initialize_db()
    import json as _json
    config_json = _json.dumps(config_dict or {})
    with _get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_runs
               (pipeline_name, direction, source_label, target_label,
                object_name, table_name, operation, status,
                records_success, records_failed, error_message,
                config_json, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pipeline_name, direction, source_label, target_label,
             object_name, table_name, operation, status,
             records_success, records_failed, error_message,
             config_json, started_at, finished_at)
        )
        conn.commit()
        return cursor.lastrowid


def update_pipeline_run(run_id, status, records_success, records_failed,
                        error_message='', finished_at=''):
    """Update an existing pipeline run after completion."""
    initialize_db()
    with _get_connection() as conn:
        conn.execute(
            """UPDATE pipeline_runs
               SET status=?, records_success=?, records_failed=?,
                   error_message=?, finished_at=?
               WHERE id=?""",
            (status, records_success, records_failed, error_message, finished_at, run_id)
        )
        conn.commit()


def list_pipeline_runs(limit=100):
    """Return all pipeline runs, newest first."""
    initialize_db()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_pipeline_run(run_id):
    """Return a single pipeline run dict by id."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE id=?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_pipeline_run(run_id):
    """Delete a pipeline run record."""
    initialize_db()
    with _get_connection() as conn:
        conn.execute("DELETE FROM pipeline_runs WHERE id=?", (run_id,))
        conn.commit()
