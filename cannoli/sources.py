"""Download (con cache locale) delle fonti dati.

Ogni funzione scarica un file in ``data/raw`` solo se non è già presente
(o se ``refresh=True``) e restituisce il percorso locale. Una volta popolata
la cache la pipeline è riproducibile offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)

_TIMEOUT = 120
_HEADERS: dict[str, str] = {}  # lo User-Agent predefinito e' accettato da tutte le fonti (IMF rifiuta alcuni UA custom)


def _download(url: str, dest: Path, refresh: bool = False, params: list[tuple[str, str]] | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not refresh:
        log.info("cache: %s", dest.name)
        return dest
    log.info("download: %s", url)
    resp = requests.get(url, params=params, timeout=_TIMEOUT, headers=_HEADERS)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


# --------------------------------------------------------------------------
# Eurostat (formato JSON-stat 2.0)
# --------------------------------------------------------------------------
def fetch_eurostat_cofog(refresh: bool = False) -> Path:
    """Spesa pubblica per funzione COFOG, tutti i paesi, in % del PIL e in milioni di euro."""
    params: list[tuple[str, str]] = [
        ("format", "JSON"),
        ("lang", "EN"),
        ("sector", "S13"),
        ("na_item", "TE"),
        ("unit", "PC_GDP"),
        ("unit", "MIO_EUR"),
    ]
    params += [("cofog99", code) for code in config.COFOG_FUNCTIONS]
    url = f"{config.EUROSTAT_API}/{config.EUROSTAT_COFOG_DATASET}"
    return _download(url, config.DATA_RAW / "eurostat_gov_10a_exp.json", refresh, params)


def fetch_eurostat_gdp(refresh: bool = False) -> Path:
    """PIL a prezzi correnti (milioni di euro), tutti i paesi."""
    params = [("format", "JSON"), ("lang", "EN"), ("unit", "CP_MEUR"), ("na_item", "B1GQ")]
    url = f"{config.EUROSTAT_API}/{config.EUROSTAT_GDP_DATASET}"
    return _download(url, config.DATA_RAW / "eurostat_nama_10_gdp.json", refresh, params)


# --------------------------------------------------------------------------
# SIPRI e NATO (file Excel)
# --------------------------------------------------------------------------
def fetch_sipri(refresh: bool = False) -> Path:
    return _download(config.SIPRI_XLSX_URL, config.DATA_RAW / "sipri_milex_1949_2025.xlsx", refresh)


def fetch_nato(refresh: bool = False) -> Path:
    return _download(config.NATO_XLSX_URL, config.DATA_RAW / "nato_def_exp_2026.xlsx", refresh)


# --------------------------------------------------------------------------
# IMF World Economic Outlook (DataMapper API)
# --------------------------------------------------------------------------
def fetch_imf(refresh: bool = False) -> Path:
    """Scarica gli indicatori WEO per l'Italia e li salva in un unico JSON locale."""
    dest = config.DATA_RAW / "imf_weo_italy.json"
    if dest.exists() and not refresh:
        log.info("cache: %s", dest.name)
        return dest
    payload: dict[str, dict] = {}
    for code in config.IMF_INDICATORS:
        url = f"{config.IMF_API}/{code}/ITA"
        log.info("download: %s", url)
        resp = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        payload[code] = data.get("values", {}).get(code, {}).get("ITA", {})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def fetch_all(refresh: bool = False) -> dict[str, Path]:
    return {
        "cofog": fetch_eurostat_cofog(refresh),
        "gdp": fetch_eurostat_gdp(refresh),
        "sipri": fetch_sipri(refresh),
        "nato": fetch_nato(refresh),
        "imf": fetch_imf(refresh),
    }
