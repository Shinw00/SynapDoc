"""XLSX 가상 EMR을 SynapDoc이 조회하는 SQLite/CSV로 변환한다."""
import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SynapDoc 가상 EMR 데이터 (환자 1).xlsx"
DB = ROOT / "support" / "emr.sqlite"
CSV_DIR = ROOT / "support" / "synthetic"


def value(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def sqlite_type(rows, index):
    values = [row[index] for row in rows if row[index] is not None]
    if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "REAL" if any(isinstance(v, float) and not v.is_integer() for v in values) else "INTEGER"
    return "TEXT"


def load_tables():
    if not SOURCE.exists():
        raise FileNotFoundError(f"XLSX 원본을 찾을 수 없습니다: {SOURCE}")
    workbook = load_workbook(SOURCE, read_only=True, data_only=True)
    tables = {}
    for sheet in workbook.worksheets:
        if sheet.title.startswith("00_"):
            continue
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(v).strip() if v is not None else f"column_{i}" for i, v in enumerate(rows[0])]
        data = [[value(v) for v in row[:len(headers)]] for row in rows[1:] if any(v is not None for v in row)]
        data = [row + [None] * (len(headers) - len(row)) for row in data]
        tables[sheet.title.split("_", 1)[-1]] = (headers, data)
    workbook.close()
    return tables


def ensure_patient_display_name(tables):
    headers, rows = tables.get("patients", ([], []))
    if "display_name" in headers or not headers:
        return
    headers.insert(1, "display_name")
    sid_index = headers.index("subject_id")
    for row in rows:
        sid = row[sid_index]
        row.insert(1, f"환자 {sid}")


def main():
    tables = load_tables()
    ensure_patient_display_name(tables)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as conn:
        for table, (headers, rows) in tables.items():
            quoted = ", ".join(f'"{h.replace(chr(34), chr(34) * 2)}" {sqlite_type(rows, i)}'
                               for i, h in enumerate(headers))
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.execute(f'CREATE TABLE "{table}" ({quoted})')
            placeholders = ",".join("?" for _ in headers)
            if rows:
                conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
            with (CSV_DIR / f"{table}.csv").open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        conn.commit()
    print(f"Imported {len(tables)} tables from {SOURCE.name} into {DB}")


if __name__ == "__main__":
    main()
