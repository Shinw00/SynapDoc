"""테스트용: test.xlsx → test.sqlite 변환.

실제 SQL 데이터가 준비되기 전까지 쓰는 임시 변환기다.
엑셀의 탭 하나가 테이블 하나가 된다 ("07_labevents" → labevents).
나머지 코드는 SQLite 만 읽으므로, 실제 DB 가 오면 .env 의 EMR_DB_PATH 만 바꾸면 된다.

    python -m support.test.load_test
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
XLSX = HERE / "test.xlsx"
DB = HERE / "test.sqlite"

# 숫자처럼 보여도 글자로 둬야 하는 컬럼
KEEP_TEXT = {"value", "icd_code", "dilution_text", "prod_strength", "gsn", "ndc",
             "anchor_year_group", "text", "comments", "field_value",
             "dose_val_rx", "form_val_disp"}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        s = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
        s = s.where(s != "", None)
        if col not in KEEP_TEXT and s.notna().any():
            num = pd.to_numeric(s, errors="coerce")
            if num[s.notna()].notna().all():          # 빈칸이 아닌 값이 전부 숫자일 때만 변환
                s = num.astype("Int64") if (num.dropna() % 1 == 0).all() else num
        df[col] = s
    return df


def build(xlsx: Path = XLSX, db: Path = DB) -> dict[str, int]:
    sheets = pd.read_excel(xlsx, sheet_name=None, dtype=str)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    counts = {}
    for name, df in sheets.items():
        if "안내" in name:
            continue
        table = re.sub(r"^\d+_", "", name.strip())
        df = _clean(df)
        df.to_sql(table, con, if_exists="replace", index=False)
        counts[table] = len(df)
    con.commit()
    con.close()
    return counts


if __name__ == "__main__":
    for table, n in build().items():
        print(f"{table:22s} {n}행")
    print(f"→ {DB}")
