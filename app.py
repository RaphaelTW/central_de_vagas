"""Central de Vagas: painel local e multi-perfil de oportunidades."""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import requests
import streamlit as st

from health_sources import HEALTH_SOURCE_CATALOG, fetch_gupy_boards

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB = DATA / "central_vagas.sqlite3"
USER_AGENT = "CentralDeVagas/1.0 (busca pessoal de oportunidades)"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "").lower()
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def words(value: str) -> set[str]:
    return set(re.findall(r"[\w+#.]{2,}", norm(value)))


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def lines(value: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in value.splitlines() if x.strip()))


def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS profiles(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL
      );
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


def profile_key(name: str) -> str:
    return hashlib.sha256(norm(name).encode()).hexdigest()[:16]


def save_profile(profile: dict) -> str:
    key = profile_key(profile["name"])
    with db() as conn:
        conn.execute("INSERT INTO profiles VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,data=excluded.data,updated_at=excluded.updated_at",
                     (key, profile["name"], json.dumps(profile, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
    return key


def get_profiles() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM profiles ORDER BY updated_at DESC").fetchall()


def request_json(url: str, params: dict | None = None) -> dict | list:
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=25)
    response.raise_for_status()
    return response.json()


def request_html(url: str, params: dict | None = None) -> str:
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=25)
    response.raise_for_status()
    return response.text


def vacancy(source: str, id_: str, title: str, company: str, location: str, url: str, description: str, remote: bool = False) -> dict | None:
    if not title or not url.startswith("http"):
        return None
    return {"key": f"{source}:{id_}", "source": source, "title": title.strip(), "company": (company or "Não informado").strip(),
            "location": (location or "Não informado").strip(), "url": url, "description": clean_html(description), "remote": remote}


def fetch_remotive(limit: int) -> Iterable[dict]:
    data = request_json("https://remotive.com/api/remote-jobs", {"limit": limit})
    for row in data.get("jobs", []):
        item = vacancy("Remotive", str(row.get("id")), row.get("title", ""), row.get("company_name", ""), row.get("candidate_required_location", "Remoto"), row.get("url", ""), row.get("description", ""), True)
        if item: yield item


def fetch_greenhouse(boards: list[str], limit: int) -> Iterable[dict]:
    for board in boards:
        data = request_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"})
        for row in data.get("jobs", [])[:limit]:
            item = vacancy("Greenhouse", f"{board}:{row.get('id')}", row.get("title", ""), board, (row.get("location") or {}).get("name", ""), row.get("absolute_url", ""), row.get("content", ""))
            if item: yield item


def fetch_lever(boards: list[str], limit: int) -> Iterable[dict]:
    for board in boards:
        data = request_json(f"https://api.lever.co/v0/postings/{board}", {"mode": "json", "limit": limit})
        for row in data:
            categories = row.get("categories") or {}
            item = vacancy("Lever", f"{board}:{row.get('id')}", row.get("text", ""), board, categories.get("location") or row.get("workplaceType", ""), row.get("hostedUrl") or row.get("applyUrl") or "", row.get("descriptionPlain") or row.get("description") or "", norm(row.get("workplaceType", "")) == "remote")
            if item: yield item


def fetch_adzuna(profile: dict, app_id: str, app_key: str, limit: int) -> Iterable[dict]:
    if not (app_id and app_key): return
    query = " OR ".join(profile["roles"][:3])
    country = profile["country"].lower()
    data = request_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", {"app_id": app_id, "app_key": app_key, "what": query, "where": profile["location"], "results_per_page": limit})
    for row in data.get("results", []):
        item = vacancy("Adzuna", str(row.get("id")), row.get("title", ""), (row.get("company") or {}).get("display_name", ""), (row.get("location") or {}).get("display_name", ""), row.get("redirect_url", ""), row.get("description", ""))
        if item: yield item


def fetch_fleury(max_pages: int = 8) -> Iterable[dict]:
    """Lê oportunidades públicas do portal oficial do Grupo Fleury em São Paulo.

    O grupo reúne marcas como Fleury, a+, Hermes Pardini e Genesis Genomics.
    Apenas consulta páginas públicas; a candidatura continua no portal oficial.
    """
    base = "https://trabalheconosco.vagas.com.br/grupo-fleury/oportunidades"
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        source = request_html(base, {"c[]": "São Paulo", "pagina": page, "q": ""})
        cards = re.findall(
            r'<a[^>]+class="[^"]*job-box[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<body>.*?)</footer>',
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not cards:
            break
        for href, body in cards:
            title_match = re.search(r'class="box__title"[^>]*>(.*?)<span', body, flags=re.IGNORECASE | re.DOTALL)
            location_match = re.search(r'class="local-wrapper".*?<p[^>]*>(.*?)</p>', body, flags=re.IGNORECASE | re.DOTALL)
            title = clean_html(title_match.group(1)) if title_match else ""
            location = clean_html(location_match.group(1)) if location_match else "São Paulo, SP"
            url = "https://trabalheconosco.vagas.com.br" + href
            key = f"Fleury:{href.rsplit('/', 1)[-1]}"
            if key in seen:
                continue
            seen.add(key)
            item = vacancy("Grupo Fleury", key, title, "Grupo Fleury / Fleury / a+ / Hermes Pardini / Genesis", location, url, title)
            if item:
                yield item


def score(job: dict, profile: dict) -> tuple[int, list[str]]:
    searchable = norm(f"{job['title']} {job['description']}")
    title_words = words(job["title"])
    role_scores = [len(words(role) & title_words) / max(1, len(words(role))) for role in profile["roles"]]
    title_score = max(role_scores, default=0)
    matched = [skill for skill in profile["skills"] if norm(skill) in searchable]
    skill_score = len(matched) / max(1, len(profile["skills"]))
    place = norm(job["location"])
    local = bool(profile["location"]) and norm(profile["location"]) in place
    remote_ok = job["remote"] or any(term in place for term in ["remote", "remoto", "worldwide", "anywhere", "global"])
    if profile["remote_only"] and not remote_ok: return 0, ["Não atende ao filtro remoto"]
    if any(norm(x) in norm(job["title"]) for x in profile["avoid"]): return 0, ["Cargo excluído no perfil"]
    score_value = round(min(100, title_score * 55 + skill_score * 35 + (10 if local or remote_ok else 0)))
    reasons = []
    if title_score: reasons.append("cargo relacionado")
    if matched: reasons.append("habilidades: " + ", ".join(matched[:4]))
    if remote_ok: reasons.append("modalidade remota")
    elif local: reasons.append("localidade compatível")
    return score_value, reasons or ["compatibilidade limitada"]


def is_preferred_location(job: dict | sqlite3.Row, profile: dict) -> bool:
    """Mantém no painel somente vagas explicitamente publicadas para a região escolhida."""
    wanted = norm(profile.get("location", ""))
    place = norm(job["location"])
    if not wanted:
        return True
    if "sao paulo" in wanted:
        city = place.split(",", 1)[0].strip()
        return city == "sao paulo"
    return wanted in place


def store_jobs(profile_id: str, jobs: list[dict], profile: dict) -> tuple[int, int]:
    now = datetime.now().isoformat(timespec="seconds")
    compatible = 0
    local_jobs = [job for job in jobs if is_preferred_location(job, profile)]
    with db() as conn:
        for job in local_jobs:
            value, reasons = score(job, profile)
            is_compatible = value >= profile["minimum_score"]
            compatible += int(is_compatible)
            status = "Novo" if is_compatible else "Baixa compatibilidade"
            conn.execute("""INSERT INTO jobs(profile_id,job_key,title,company,location,source,url,description,score,reasons,status,found_at,first_seen)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(profile_id,job_key) DO UPDATE SET
                title=excluded.title,company=excluded.company,location=excluded.location,url=excluded.url,description=excluded.description,score=excluded.score,reasons=excluded.reasons,found_at=excluded.found_at""",
                (profile_id, job["key"], job["title"], job["company"], job["location"], job["source"], job["url"], job["description"], value, "; ".join(reasons), status, now, now))
    return len(local_jobs), compatible


@st.cache_data(ttl="10m")
def load_public_feed() -> list[dict]:
    path = DATA / "vagas_publicas.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("jobs", [])
    except (OSError, json.JSONDecodeError):
        return []


st.set_page_config(page_title="Central de Vagas", page_icon="🔎", layout="wide")
DEFAULT_PROFILE = {
    "name": "Letícia Maia — Laboratório",
    "roles": ["Técnica de laboratório", "Técnica em química", "Analista de laboratório", "Técnica em toxicologia"],
    "skills": ["HPLC", "Cromatografia líquida", "Toxicologia", "Controle de estoque", "Preparo de soluções", "Validação de métodos", "ISO 17025", "Preparo de amostras", "Qualificação de instrumentos"],
    "location": "São Paulo - SP",
    "country": "br",
    "remote_only": False,
    "minimum_score": 55,
    "avoid": ["estágio", "internship"],
}
st.title("Central de Vagas")
st.caption("Encontre oportunidades por perfil — para qualquer área, sem automatizar candidaturas.")

with st.sidebar:
    st.header("Perfil usado pelo agente")
    st.caption("Edite apenas se quiser mudar a pessoa ou a área. O perfil da Letícia já está pronto.")
    existing = get_profiles()
    selected = st.selectbox("Perfil salvo", ["Novo perfil"] + [row["name"] for row in existing])
    saved = next((row for row in existing if row["name"] == selected), None)
    # Perfil inicial extraído do currículo Profile.pdf fornecido pelo usuário.
    base = json.loads(saved["data"]) if saved else DEFAULT_PROFILE
    name = st.text_input("Nome do perfil", value=base.get("name", ""), placeholder="Ex.: Marina — Marketing")
    roles_raw = st.text_area("Cargos desejados (um por linha)", value="\n".join(base.get("roles", [])), placeholder="Analista de Marketing\nSocial Media")
    skills_raw = st.text_area("Habilidades (uma por linha)", value="\n".join(base.get("skills", [])), placeholder="SEO\nGoogle Analytics\nCanva")
    location = st.text_input("Cidade/região preferida", value=base.get("location", "Brasil"))
    country = st.selectbox("País para Adzuna", ["br", "pt", "us", "gb"], index=["br", "pt", "us", "gb"].index(base.get("country", "br")))
    remote_only = st.checkbox("Somente remoto", value=base.get("remote_only", False))
    minimum = st.slider("Compatibilidade mínima", 20, 95, base.get("minimum_score", 55), 5)
    avoid_raw = st.text_input("Excluir títulos contendo", value=", ".join(base.get("avoid", ["estágio"])))
    profile = {"name": name.strip(), "roles": lines(roles_raw), "skills": lines(skills_raw), "location": location.strip(), "country": country,
               "remote_only": remote_only, "minimum_score": minimum, "avoid": [x.strip() for x in avoid_raw.split(",") if x.strip()]}
    if st.button("Salvar alterações do perfil", width="stretch", icon=":material/save:"):
        if not profile["name"] or not profile["roles"]:
            st.error("Informe um nome e pelo menos um cargo desejado.")
        else:
            st.session_state.profile_id = save_profile(profile)
            st.success("Perfil salvo neste computador.")

profile_id = st.session_state.get("profile_id") or (saved["id"] if saved else None)
if not profile_id and profile["name"]:
    profile_id = save_profile(profile)
    st.session_state.profile_id = profile_id

# Em hospedagens, este catálogo é atualizado diariamente pelo GitHub Actions.
public_feed = load_public_feed()
if profile_id and public_feed:
    store_jobs(profile_id, public_feed, profile)

tab_find, tab_board, tab_sources, tab_help = st.tabs(["Agente de vagas", "Vagas encontradas", "Fontes de saúde", "Ajuda simples"])

with tab_find:
    st.subheader("Agente de vagas pronto")
    with st.container(border=True):
        st.write(f"**Procurando para:** {profile['name']}")
        st.caption("O agente busca vagas publicadas para São Paulo - SP, incluindo Fleury, a+, Hermes Pardini e Genesis Genomics. Ele organiza todas no painel e coloca as mais compatíveis no topo.")
        run_search = st.button("Procurar vagas agora", type="primary", width="stretch", icon=":material/search:", key="search_jobs")
    with st.expander("Opções avançadas (não precisa preencher)"):
        st.caption("Deixe em branco para usar apenas a busca pública padrão. Só use estes campos se já conhecer empresas específicas ou possuir chaves da Adzuna.")
        col1, col2 = st.columns(2)
        with col1:
            greenhouse = st.text_area("Empresas Greenhouse (uma por linha)", placeholder="Deixe vazio", key="greenhouse_boards")
            lever = st.text_area("Empresas Lever (uma por linha)", placeholder="Deixe vazio", key="lever_boards")
        with col2:
            adzuna_id = st.text_input("Adzuna App ID", type="password", key="adzuna_id")
            adzuna_key = st.text_input("Adzuna App Key", type="password", key="adzuna_key")
            limit = st.slider("Máximo por fonte", 10, 100, 30, 10, key="source_limit")
    # Valores seguros fora das opções avançadas para a primeira busca.
    greenhouse = st.session_state.get("greenhouse_boards", "")
    lever = st.session_state.get("lever_boards", "")
    adzuna_id = st.session_state.get("adzuna_id", "")
    adzuna_key = st.session_state.get("adzuna_key", "")
    limit = st.session_state.get("source_limit", 30)
    if run_search:
        if not profile_id or not profile["roles"]:
            st.error("Salve ou selecione um perfil com cargos desejados antes de buscar.")
        else:
            all_jobs, errors = [], []
            sources = [("Grupo Fleury", lambda: fetch_fleury()), ("Dasa, Eurofarma e Rede D'Or", lambda: fetch_gupy_boards()), ("Remotive", lambda: fetch_remotive(limit)), ("Greenhouse", lambda: fetch_greenhouse(lines(greenhouse), limit)), ("Lever", lambda: fetch_lever(lines(lever), limit))]
            if adzuna_id and adzuna_key: sources.append(("Adzuna", lambda: fetch_adzuna(profile, adzuna_id, adzuna_key, limit)))
            progress = st.progress(0, text="Consultando fontes públicas…")
            for index, (label, source) in enumerate(sources, 1):
                try: all_jobs.extend(source())
                except requests.RequestException as exc: errors.append(f"{label}: {exc}")
                progress.progress(index / len(sources), text=f"Consultando {label}…")
            unique = {job["key"]: job for job in all_jobs}
            total, compatible = store_jobs(profile_id, list(unique.values()), profile)
            progress.empty()
            st.success(f"Pronto: encontrei {total} vagas para São Paulo - SP, entre {len(unique)} vagas consultadas. {compatible} ficaram no topo como mais compatíveis.")
            st.info("Abra a aba **Vagas encontradas** para ver todas as oportunidades, inclusive as de baixa compatibilidade.")
            for error in errors: st.warning(error)

with tab_board:
    if not profile_id:
        st.info("Salve ou escolha um perfil para ver seu painel.")
    else:
        with db() as conn:
            rows = conn.execute("SELECT * FROM jobs WHERE profile_id=? ORDER BY score DESC, found_at DESC", (profile_id,)).fetchall()
        local_rows = [row for row in rows if is_preferred_location(row, profile)]
        new_cutoff = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        new_since_yesterday = sum(bool(row["first_seen"] and row["first_seen"] >= new_cutoff) for row in local_rows)
        a, b, c = st.columns(3)
        a.metric("Vagas encontradas", len(local_rows)); b.metric("Novas nas últimas 24h", new_since_yesterday); c.metric("Candidaturas marcadas", sum(row["status"] == "Candidatura enviada" for row in local_rows))
        wanted = st.multiselect("Mostrar", ["Novo", "Baixa compatibilidade", "Salva", "Revisar", "Candidatura enviada", "Descartada"], default=["Novo", "Baixa compatibilidade", "Salva", "Revisar", "Candidatura enviada"], key="status_filter")
        shown = [row for row in local_rows if row["status"] in wanted]
        if not shown: st.info("Ainda não há vagas neste filtro. Faça uma busca ou ajuste os filtros.")
        for row in shown:
            with st.expander(f"{row['score']}% · {row['title']} — {row['company']} ({row['source']})"):
                st.write(f"**Local:** {row['location']}  ")
                st.caption("Match: " + row["reasons"])
                st.write((row["description"][:600] + "…") if len(row["description"]) > 600 else row["description"])
                x, y = st.columns([2, 1])
                x.link_button("Abrir vaga original", row["url"], width="stretch")
                status_options = ["Novo", "Baixa compatibilidade", "Salva", "Revisar", "Candidatura enviada", "Descartada"]
                new_status = y.selectbox("Status", status_options, index=status_options.index(row["status"]) if row["status"] in status_options else 0, key=f"status-{row['job_key']}")
                if new_status != row["status"]:
                    with db() as conn: conn.execute("UPDATE jobs SET status=? WHERE profile_id=? AND job_key=?", (new_status, profile_id, row["job_key"]))
                    st.rerun()

with tab_sources:
    st.subheader("Rede de fontes em saúde")
    st.caption("O agente consulta automaticamente as fontes públicas compatíveis. As demais ficam catalogadas para integração quando houver um feed público estável; assim não tentamos burlar logins, CAPTCHAs ou portais privados.")
    automated = sum(status == "Automática" for _, _, status in HEALTH_SOURCE_CATALOG)
    st.metric("Fontes catalogadas", len(HEALTH_SOURCE_CATALOG), delta=f"{automated} automatizadas")
    groups: dict[str, list[tuple[str, str]]] = {}
    for category, name, status in HEALTH_SOURCE_CATALOG:
        groups.setdefault(category, []).append((name, status))
    for category, entries in groups.items():
        with st.expander(category, expanded=True):
            for name, status in entries:
                st.write(f":material/check_circle: **{name}** - {status}")

with tab_help:
    st.markdown("""### Uso em dois passos
1. Na aba **Agente de vagas**, clique em **Procurar vagas agora**.
2. Na aba **Vagas encontradas**, abra as vagas e marque o que quer revisar ou onde já se candidatou.

### Transparência e segurança
A nota ajuda a organizar a lista: quanto maior, mais palavras da vaga combinam com o perfil. Mesmo as vagas com nota baixa continuam visíveis. O agente não envia currículo nem candidatura; a pessoa decide ao abrir o site original.
""")
