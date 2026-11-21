"""Exporta o catálogo diário de vagas para ser consumido pela versão hospedada."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "central_vagas.sqlite3"
OUTPUT = DATA / "vagas_publicas.json"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT job_key AS key, source, title, company, location, url, description
                           FROM jobs WHERE profile_id='public-health-sp'
                           ORDER BY found_at DESC""").fetchall()
    jobs = [dict(row) | {"remote": False} for row in rows]
    OUTPUT.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Catálogo público exportado: {len(jobs)} vagas")


if __name__ == "__main__":
    main()
