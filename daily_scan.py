"""Atualização diária sem interface da Central de Vagas."""
from __future__ import annotations

import html
import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

from health_sources import fetch_gupy_boards

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "central_vagas.sqlite3"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "").lower()
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def words(value: str) -> set[str]:
    return set(re.findall(r"[\w+#.]{2,}", norm(value)))


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS jobs(
        profile_id TEXT NOT NULL, job_key TEXT NOT NULL, title TEXT NOT NULL, company TEXT,
        location TEXT, source TEXT, url TEXT NOT NULL, description TEXT, score INTEGER NOT NULL,
        reasons TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Novo', found_at TEXT NOT NULL, first_seen TEXT,
        PRIMARY KEY(profile_id, job_key)
      );
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "first_seen" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN first_seen TEXT")
        conn.execute("UPDATE jobs SET first_seen=found_at WHERE first_seen IS NULL")
    return conn


def get_profile(conn: sqlite3.Connection) -> tuple[str, dict]:
    row = conn.execute("SELECT id,data FROM profiles ORDER BY updated_at DESC LIMIT 1").fetchone()
    if not row:
        raise RuntimeError("Abra a Central de Vagas e salve o perfil antes da primeira atualização automática.")
    return row["id"], json.loads(row["data"])


def fetch_fleury() -> list[dict]:
    base = "https://trabalheconosco.vagas.com.br/grupo-fleury/oportunidades"
    output, seen = [], set()
    for page in range(1, 9):
        response = requests.get(base, params={"c[]": "São Paulo", "pagina": page, "q": ""}, headers={"User-Agent": "CentralDeVagas/1.0"}, timeout=30)
        response.raise_for_status()
        cards = re.findall(r'<a[^>]+class="[^"]*job-box[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<body>.*?)</footer>', response.text, flags=re.I | re.S)
        if not cards:
            break
        for href, body in cards:
            title_hit = re.search(r'class="box__title"[^>]*>(.*?)<span', body, flags=re.I | re.S)
            place_hit = re.search(r'class="local-wrapper".*?<p[^>]*>(.*?)</p>', body, flags=re.I | re.S)
            title = clean(title_hit.group(1)) if title_hit else ""
            location = clean(place_hit.group(1)) if place_hit else "São Paulo, SP"
            key = f"Grupo Fleury:Fleury:{href.rsplit('/', 1)[-1]}"
            if not title or key in seen or "sao paulo" not in norm(location):
                continue
            seen.add(key)
            output.append({"key": key, "title": title, "location": location, "url": "https://trabalheconosco.vagas.com.br" + href})
    return output


def score(job: dict, profile: dict) -> tuple[int, str]:
    title_words = words(job["title"])
    title_score = max((len(words(role) & title_words) / max(1, len(words(role))) for role in profile.get("roles", [])), default=0)
    searchable = norm(job["title"])
    matched = [skill for skill in profile.get("skills", []) if norm(skill) in searchable]
    value = round(min(100, title_score * 55 + len(matched) / max(1, len(profile.get("skills", []))) * 35 + 10))
    reasons = ["cargo relacionado"] if title_score else []
    if matched:
        reasons.append("habilidades: " + ", ".join(matched[:4]))
    reasons.append("São Paulo - SP")
    return value, "; ".join(reasons)


def main() -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        profile_id, profile = get_profile(conn)
        before = {row[0] for row in conn.execute("SELECT job_key FROM jobs WHERE profile_id=?", (profile_id,))}
        jobs = fetch_fleury() + list(fetch_gupy_boards())
        new_count = 0
        for job in jobs:
            value, reasons = score(job, profile)
            if job["key"] not in before:
                new_count += 1
            status = "Novo" if value >= int(profile.get("minimum_score", 55)) else "Baixa compatibilidade"
            conn.execute("""INSERT INTO jobs(profile_id,job_key,title,company,location,source,url,description,score,reasons,status,found_at,first_seen)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(profile_id,job_key) DO UPDATE SET
              title=excluded.title,location=excluded.location,url=excluded.url,score=excluded.score,reasons=excluded.reasons,found_at=excluded.found_at""",
              (profile_id, job["key"], job["title"], "Grupo Fleury / Fleury / a+ / Hermes Pardini / Genesis", job["location"], "Grupo Fleury", job["url"], job["title"], value, reasons, status, now, now))
    message = f"{now} | Atualização concluída: {len(jobs)} vagas consultadas em São Paulo, {new_count} novas."
    print(message)
    (DATA / "daily_scan.log").open("a", encoding="utf-8").write(message + "\n")


if __name__ == "__main__":
    main()
