"""Conversione delle fonti grezze in tabelle tidy (una riga per osservazione).

Ogni funzione ``load_*`` legge il file in ``data/raw``, scrive un CSV in
``data/processed`` e restituisce il DataFrame per la pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .countries import BY_NATO, BY_SIPRI, NATO_AGGREGATES, clean_nato_name, name_it

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# JSON-stat -> DataFrame
# --------------------------------------------------------------------------
def jsonstat_to_frame(data: dict) -> pd.DataFrame:
    """Converte una risposta JSON-stat 2.0 di Eurostat in un DataFrame tidy.

    I valori sono indicizzati in modo "piatto" (row-major sulle dimensioni
    elencate in ``data["id"]``); le coordinate si ricostruiscono con
    ``np.unravel_index``.
    """
    dims = data["id"]
    sizes = data["size"]
    categories = {dim: [code for code, _ in sorted(data["dimension"][dim]["category"]["index"].items(), key=lambda kv: kv[1])] for dim in dims}
    flat_idx = np.array([int(k) for k in data["value"].keys()], dtype=int)
    values = np.array(list(data["value"].values()), dtype=float)
    coords = np.unravel_index(flat_idx, sizes)
    frame = pd.DataFrame({dim: np.array(categories[dim])[coords[i]] for i, dim in enumerate(dims)})
    frame["value"] = values
    return frame


def _write(df: pd.DataFrame, name: str) -> pd.DataFrame:
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out = config.DATA_PROCESSED / name
    df.to_csv(out, index=False, encoding="utf-8")
    log.info("scritto %s (%d righe)", out.name, len(df))
    return df.reset_index(drop=True)


def load_eurostat_cofog(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    df = jsonstat_to_frame(data).rename(columns={"cofog99": "cofog", "time": "year"})
    df["year"] = df["year"].astype(int)
    df["function"] = df["cofog"].map(config.COFOG_FUNCTIONS)
    df["country"] = df["geo"].map(name_it)
    df = df[["geo", "country", "year", "cofog", "function", "unit", "value"]]
    return _write(df.sort_values(["geo", "cofog", "unit", "year"]), "eurostat_cofog.csv")


def load_eurostat_gdp(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    df = jsonstat_to_frame(data).rename(columns={"time": "year", "value": "gdp_meur"})
    df["year"] = df["year"].astype(int)
    df["country"] = df["geo"].map(name_it)
    df = df[["geo", "country", "year", "gdp_meur"]]
    return _write(df.sort_values(["geo", "year"]), "eurostat_gdp.csv")


# --------------------------------------------------------------------------
# SIPRI
# --------------------------------------------------------------------------
def _sipri_sheet(path: Path, sheet: str, header: int, measure: str, scale: float) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=header)
    raw = raw.rename(columns={raw.columns[0]: "sipri_name"})
    year_cols = [c for c in raw.columns if isinstance(c, (int, float)) and 1900 < float(c) < 2100]
    raw = raw[raw["sipri_name"].isin(BY_SIPRI)]
    long = raw.melt(id_vars=["sipri_name"], value_vars=year_cols, var_name="year", value_name="value")
    long["year"] = long["year"].astype(int)
    # "..." (dato mancante) e "xxx" (paese inesistente) diventano NaN
    long["value"] = pd.to_numeric(long["value"], errors="coerce") * scale
    long = long.dropna(subset=["value"])
    long["measure"] = measure
    return long


def load_sipri(path: Path) -> pd.DataFrame:
    frames = [_sipri_sheet(path, sheet, **spec) for sheet, spec in config.SIPRI_SHEETS.items()]
    df = pd.concat(frames, ignore_index=True)
    df["geo"] = df["sipri_name"].map(lambda n: BY_SIPRI[n].geo)
    df["country"] = df["geo"].map(name_it)
    df = df[["geo", "country", "year", "measure", "value"]]
    return _write(df.sort_values(["measure", "geo", "year"]), "sipri_milex.csv")


# --------------------------------------------------------------------------
# NATO
# --------------------------------------------------------------------------
# (foglio, titolo del blocco) -> nome della misura
NATO_MEASURES: dict[tuple[str, str], str] = {
    ("Table 1", "Current prices"): "core_nat_currency_current_m",
    ("Table 1", "Constant 2021 prices"): "core_nat_currency_2021_m",
    ("Table 2", "Current prices and exchange rates"): "core_usd_current_m",
    ("Table 2", "Constant 2021 prices and exchange rates"): "core_usd_2021_m",
    ("Table 3", "Share of real GDP (%)"): "core_share_gdp",
    ("Table 3", "Annual real change (%)"): "core_real_change_pct",
    ("Table 5", "Current prices and exchange rates"): "gdp_usd_current_m",
    ("Table 5", "Constant 2021 prices and exchange rates"): "gdp_usd_2021_m",
    ("Table 6", "GDP per capita (thousand US dollars)"): "gdp_per_capita_2021_kusd",
    ("Table 6", "Core defence expenditure per capita (US dollars)"): "core_per_capita_2021_usd",
    ("Table 7", "Thousands"): "personnel_k",
    ("Table 8a", "Equipment (a)"): "equipment_share_pct",
    ("Table 8a", "Personnel (b)"): "personnel_share_pct",
    ("Table 8b", "Infrastructure (c)"): "infrastructure_share_pct",
    ("Table 8b", "Other (d)"): "other_share_pct",
}


def _nato_blocks(rows: list[tuple]) -> list[tuple[str, list, list[tuple]]]:
    """Spezza un foglio NATO in blocchi (titolo, intestazione anni, righe dati).

    Un blocco inizia con la riga d'intestazione (la cella B vale 2014); il
    titolo del blocco è la riga di solo testo immediatamente precedente.
    """
    blocks: list[tuple[str, list, list[tuple]]] = []
    title = ""
    i = 0
    while i < len(rows):
        row = rows[i]
        if row[1] == 2014:
            header = list(row)
            body: list[tuple] = []
            j = i + 1
            while j < len(rows) and rows[j][0] not in (None, "") and not str(rows[j][0]).startswith("Notes"):
                body.append(rows[j])
                j += 1
            blocks.append((title, header, body))
            i = j
            continue
        if row[0] not in (None, "") and all(c in (None, "") for c in row[1:]):
            title = str(row[0]).strip()
        i += 1
    return blocks


def load_nato(path: Path) -> pd.DataFrame:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = list(dict.fromkeys(sheet for sheet, _ in NATO_MEASURES))
    records: list[dict] = []
    for sheet in sheets:
        rows = list(wb[sheet].iter_rows(values_only=True))
        for title, header, body in _nato_blocks(rows):
            measure = NATO_MEASURES.get((sheet, title))
            if measure is None:
                continue
            year_cols = [(idx, str(h)) for idx, h in enumerate(header) if idx > 0 and h not in (None, "")]
            for row in body:
                name = clean_nato_name(str(row[0]))
                if name in NATO_AGGREGATES:
                    geo = NATO_AGGREGATES[name]
                elif name in BY_NATO:
                    geo = BY_NATO[name].geo
                else:
                    continue
                for idx, label in year_cols:
                    val = row[idx]
                    if val is None or isinstance(val, str):
                        continue
                    records.append(
                        {
                            "geo": geo,
                            "country": name_it(geo),
                            "year": int(label.rstrip("e")),
                            "estimate": label.endswith("e"),
                            "measure": measure,
                            "value": float(val),
                        }
                    )
    df = pd.DataFrame.from_records(records)
    return _write(df.sort_values(["measure", "geo", "year"]), "nato_defence.csv")


# --------------------------------------------------------------------------
# IMF
# --------------------------------------------------------------------------
def load_imf(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [
        {"year": int(year), "indicator": code, "label": config.IMF_INDICATORS[code], "value": float(val)}
        for code, series in payload.items()
        for year, val in series.items()
        if val is not None
    ]
    df = pd.DataFrame.from_records(records)
    return _write(df.sort_values(["indicator", "year"]), "imf_weo_italy.csv")


def load_all(paths: dict[str, Path]) -> dict[str, pd.DataFrame]:
    return {
        "cofog": load_eurostat_cofog(paths["cofog"]),
        "gdp": load_eurostat_gdp(paths["gdp"]),
        "sipri": load_sipri(paths["sipri"]),
        "nato": load_nato(paths["nato"]),
        "imf": load_imf(paths["imf"]),
    }


def read_processed() -> dict[str, pd.DataFrame]:
    """Rilegge i CSV già prodotti (per rigenerare grafici senza ritrasformare)."""
    names = {
        "cofog": "eurostat_cofog.csv",
        "gdp": "eurostat_gdp.csv",
        "sipri": "sipri_milex.csv",
        "nato": "nato_defence.csv",
        "imf": "imf_weo_italy.csv",
    }
    return {key: pd.read_csv(config.DATA_PROCESSED / fname, encoding="utf-8") for key, fname in names.items()}
