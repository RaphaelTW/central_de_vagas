"""Fontes públicas de saúde monitoradas pela Central de Vagas."""
from __future__ import annotations

import html
import json
import re
from typing import Iterable

import requests


AUTOMATED_GUPY_BOARDS = (
    ("Dasa", "https://dasaatendimento.gupy.io/"),
    ("Eurofarma", "https://eurofarma.gupy.io/"),
    ("Rede D'Or", "https://rededor.gupy.io/"),
)

HEALTH_SOURCE_CATALOG = (
    ("Laboratórios e diagnóstico", "Grupo Fleury", "Automática"),
    ("Laboratórios e diagnóstico", "Dasa", "Automática"),
    ("Laboratórios e diagnóstico", "Grupo Sabin", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "DB Diagnósticos", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "SGS", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "Eurofins", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "Mérieux NutriSciences", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "ALS Life Sciences", "Acompanhar portal oficial"),
    ("Laboratórios e diagnóstico", "Bureau Veritas", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Eurofarma", "Automática"),
    ("Farmacêuticas e pesquisa", "Aché Laboratórios", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Libbs Farmacêutica", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Biolab Farmacêutica", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Blau Farmacêutica", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "União Química", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Laboratório Cristália", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "EMS", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Hypera Pharma", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Fundação Butantan", "Acompanhar portal oficial"),
    ("Farmacêuticas e pesquisa", "Pfizer", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "Hospital Israelita Albert Einstein", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "Hospital Sírio-Libanês", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "Rede D'Or", "Automática"),
    ("Hospitais e saúde", "Hospital Alemão Oswaldo Cruz", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "A.C.Camargo Cancer Center", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "BP - Beneficência Portuguesa", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "Hcor", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "Hospital São Camilo", "Acompanhar portal oficial"),
    ("Hospitais e saúde", "LIM - HC/FMUSP", "Acompanhar portal oficial"),
)


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _walk_for_jobs(value: object) -> list[dict]:
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        if any("title" in item and "workplace" in item for item in value):
            return value
    if isinstance(value, dict):
        for child in value.values():
            found = _walk_for_jobs(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _walk_for_jobs(child)
            if found:
                return found
    return []


def fetch_gupy_boards() -> Iterable[dict]:
    """Lê apenas dados de vagas já expostos nas páginas públicas dos boards."""
    for company, board_url in AUTOMATED_GUPY_BOARDS:
        response = requests.get(board_url, headers={"User-Agent": "CentralDeVagas/1.0"}, timeout=30)
        response.raise_for_status()
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text, re.S)
        if not match:
            continue
        jobs = _walk_for_jobs(json.loads(match.group(1)))
        for job in jobs:
            address = ((job.get("workplace") or {}).get("address") or {})
            city = address.get("city") or ""
            state = address.get("stateShortName") or address.get("state") or ""
            location = ", ".join(part for part in (city, state) if part) or "Não informado"
            if _text(city).lower().replace("ã", "a") != "sao paulo":
                continue
            job_id = str(job.get("id") or job.get("code") or job.get("title"))
            title = _text(str(job.get("title") or ""))
            if title:
                yield {
                    "key": f"Gupy:{company}:{job_id}", "source": company, "title": title, "company": company,
                    "location": location, "url": board_url, "description": title, "remote": False,
                }
