"""협진 이력 저장소. EMR 과 별도의 DB 파일이며, 여기에만 쓰기가 일어난다.

발송한 의뢰서와 받은 회신을 저장해 두고, 재협진 때 이전 건을 찾는 데 쓴다.
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


def _path() -> Path:
    p = Path(os.getenv("CONSULT_DB_PATH", "support/consults.sqlite"))
    return p if p.is_absolute() else ROOT / p


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(_path())
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS consults (
            consult_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT, subject_id INTEGER, hadm_id INTEGER,
            requesting_dept TEXT, requester TEXT, target_dept TEXT, recipient TEXT,
            urgency TEXT, as_of TEXT, request_text TEXT,
            document_text TEXT, document_json TEXT, mail_json TEXT,
            status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            consult_id INTEGER, replier TEXT, replied_at TEXT, text TEXT);
    """)
    return con


def save_consult(**row) -> int:
    row = {**row, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    for k in ("document_json", "mail_json"):
        if not isinstance(row.get(k), str):
            row[k] = json.dumps(row.get(k), ensure_ascii=False)
    cols = ", ".join(row)
    con = _con()
    with con:
        cur = con.execute(f"INSERT INTO consults ({cols}) VALUES ({', '.join('?' for _ in row)})",
                          tuple(row.values()))
    con.close()
    return cur.lastrowid


def add_reply(consult_id: int, replier: str, text: str, replied_at: str) -> int:
    con = _con()
    with con:
        cur = con.execute("INSERT INTO replies (consult_id, replier, replied_at, text) VALUES (?,?,?,?)",
                          (consult_id, replier, replied_at, text))
    con.close()
    return cur.lastrowid


def get_consult(consult_id: int) -> dict | None:
    con = _con()
    row = con.execute("SELECT * FROM consults WHERE consult_id=?", (consult_id,)).fetchone()
    if not row:
        con.close()
        return None
    out = dict(row)
    out["replies"] = [dict(r) for r in con.execute(
        "SELECT * FROM replies WHERE consult_id=? ORDER BY replied_at", (consult_id,))]
    con.close()
    return out


def get_by_thread(thread_id: str) -> dict | None:
    con = _con()
    row = con.execute("SELECT consult_id FROM consults WHERE thread_id=?", (thread_id,)).fetchone()
    con.close()
    return get_consult(row["consult_id"]) if row else None


def list_for_patient(subject_id: int, target_dept: str | None = None,
                     before: str | None = None) -> list[dict]:
    """환자의 발송된 협진 이력. before 를 주면 그 시점보다 앞선 것만 (재협진 판단용)."""
    sql, params = "SELECT consult_id FROM consults WHERE subject_id=? AND status='sent'", [subject_id]
    if target_dept:
        sql += " AND target_dept=?"
        params.append(target_dept)
    if before:
        sql += " AND as_of<?"
        params.append(before)
    con = _con()
    ids = [r["consult_id"] for r in con.execute(sql + " ORDER BY as_of", tuple(params))]
    con.close()
    return [get_consult(i) for i in ids]
