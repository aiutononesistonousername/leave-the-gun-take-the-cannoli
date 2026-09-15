"""Proiezione del PIL italiano e scenari di spesa militare 2026-2035.

Modello volutamente semplice e trasparente:

1. **PIL nominale**. Si parte dal PIL dell'ultimo anno effettivo (Eurostat) e
   lo si fa crescere con la crescita reale e l'inflazione previste dal FMI
   (World Economic Outlook) fino all'ultimo anno disponibile; oltre, si
   mantengono i valori dell'ultimo anno. L'inflazione al consumo è usata come
   approssimazione del deflatore del PIL. Lo stesso indice dei prezzi serve a
   riportare gli importi a prezzi costanti (base = ultimo anno effettivo).
2. **Scenari** (definizione NATO, quota "core" + quota "related"): ogni
   scenario è una traiettoria annua in % del PIL, convertita in euro con il
   PIL proiettato. Gli importi sono quindi a prezzi correnti; le colonne
   ``*_const`` sono deflazionate.
3. **Costo aggiuntivo**: differenza rispetto allo scenario base (quota 2026
   costante), anno per anno e cumulata. È confrontato con sanità e istruzione
   proiettate a quota di PIL costante (ultimo dato Eurostat COFOG), sia come
   percentuale del bilancio dell'anno sia come "anni di bilancio" (somma dei
   rapporti annui, che non dipende dall'inflazione).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config
from .config import Scenario

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# PIL nominale e indice dei prezzi
# --------------------------------------------------------------------------
def project_gdp(gdp_eurostat: pd.DataFrame, imf: pd.DataFrame, end_year: int = config.TARGET_YEAR) -> pd.DataFrame:
    """Serie annua del PIL nominale italiano (miliardi di euro) fino a ``end_year``.

    Colonne: real_growth, inflation, nominal_growth (in %), gdp_bn,
    price_index (1,0 nell'ultimo anno effettivo), source.
    """
    actual = gdp_eurostat[gdp_eurostat["geo"] == config.FOCUS_COUNTRY].set_index("year")["gdp_meur"].div(1000.0).dropna().sort_index()
    last_actual = int(actual.index.max())

    growth = imf[imf["indicator"] == "NGDP_RPCH"].set_index("year")["value"].sort_index()
    inflation = imf[imf["indicator"] == "PCPIPCH"].set_index("year")["value"].sort_index()
    last_imf = int(min(growth.index.max(), inflation.index.max()))

    rows = [
        {
            "year": int(y),
            "real_growth": np.nan,
            "inflation": np.nan,
            "nominal_growth": np.nan,
            "gdp_bn": float(v),
            "price_index": 1.0 if int(y) == last_actual else np.nan,
            "source": "Eurostat",
        }
        for y, v in actual.items()
    ]
    level = float(actual.loc[last_actual])
    index = 1.0
    for year in range(last_actual + 1, end_year + 1):
        ref = min(year, last_imf)
        g = float(growth.loc[ref]) / 100.0
        p = float(inflation.loc[ref]) / 100.0
        nominal = (1 + g) * (1 + p) - 1
        level *= 1 + nominal
        index *= 1 + p
        rows.append(
            {
                "year": year,
                "real_growth": g * 100,
                "inflation": p * 100,
                "nominal_growth": nominal * 100,
                "gdp_bn": level,
                "price_index": index,
                "source": "FMI WEO" if year <= last_imf else "estrapolazione (ultimo anno FMI)",
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Traiettorie in % del PIL
# --------------------------------------------------------------------------
def linear_path(start_year: int, start_value: float, end_year: int, end_value: float) -> dict[int, float]:
    """Interpolazione lineare inclusa di entrambi gli estremi."""
    years = list(range(start_year, end_year + 1))
    values = np.linspace(start_value, end_value, len(years))
    return {y: float(v) for y, v in zip(years, values, strict=False)}


def piecewise_path(waypoints: dict[int, float]) -> dict[int, float]:
    """Interpolazione lineare a tratti tra punti (anno -> valore)."""
    years = sorted(waypoints)
    out: dict[int, float] = {}
    for a, b in zip(years, years[1:], strict=False):
        out.update(linear_path(a, waypoints[a], b, waypoints[b]))
    out[years[-1]] = waypoints[years[-1]]
    return out


def scenario_shares(scenario: Scenario) -> pd.DataFrame:
    """Quote annue core/related/totale in % del PIL per uno scenario."""
    start = config.FIRST_PROJECTION_YEAR
    end = config.TARGET_YEAR
    years = list(range(start, end + 1))

    core = {y: config.START_CORE_SHARE for y in years}
    related = {y: config.START_RELATED_SHARE for y in years}

    if scenario.core_target is not None:
        core = linear_path(start, config.START_CORE_SHARE, end, scenario.core_target)

    if scenario.waypoints:
        total = piecewise_path(scenario.waypoints)
        # La componente related sale linearmente fino all'obiettivo NATO (1,5%);
        # il core è la differenza e arriva così al 3,5% nel 2035.
        related = linear_path(start, config.START_RELATED_SHARE, end, config.NATO_RELATED_TARGET)
        core = {y: total[y] - related[y] for y in years}

    df = pd.DataFrame(
        {
            "year": years,
            "scenario": scenario.key,
            "label": scenario.label,
            "core_share": [core[y] for y in years],
            "related_share": [related[y] for y in years],
        }
    )
    df["total_share"] = df["core_share"] + df["related_share"]
    return df


# --------------------------------------------------------------------------
# Scenari completi in euro e confronti
# --------------------------------------------------------------------------
def comparator_shares(cofog: pd.DataFrame) -> dict[str, tuple[int, float]]:
    """Ultima quota di PIL disponibile per le voci COFOG di confronto: codice -> (anno, valore)."""
    it = cofog[(cofog["geo"] == config.FOCUS_COUNTRY) & (cofog["unit"] == "PC_GDP")]
    out: dict[str, tuple[int, float]] = {}
    for code in config.COMPARATORS:
        series = it[it["cofog"] == code].dropna(subset=["value"]).sort_values("year")
        out[code] = (int(series["year"].iloc[-1]), float(series["value"].iloc[-1]))
    return out


def build_scenarios(gdp: pd.DataFrame, cofog: pd.DataFrame, imf: pd.DataFrame) -> pd.DataFrame:
    """Tabella lunga anno x scenario con quote, euro correnti e costanti, extra-costo e confronti."""
    frames = [scenario_shares(s) for s in config.SCENARIOS]
    df = pd.concat(frames, ignore_index=True)
    df = df.merge(gdp[["year", "gdp_bn", "price_index"]], on="year", how="left")
    df["core_bn"] = df["core_share"] / 100 * df["gdp_bn"]
    df["related_bn"] = df["related_share"] / 100 * df["gdp_bn"]
    df["total_bn"] = df["total_share"] / 100 * df["gdp_bn"]

    base = df[df["scenario"] == "baseline"].set_index("year")["total_bn"]
    df["extra_vs_baseline_bn"] = df["total_bn"] - df["year"].map(base)
    df["cumulative_extra_bn"] = df.groupby("scenario")["extra_vs_baseline_bn"].cumsum()

    # Prezzi costanti (base = ultimo anno effettivo di PIL)
    for col in ["core_bn", "related_bn", "total_bn", "extra_vs_baseline_bn"]:
        df[f"{col}_const"] = df[col] / df["price_index"]
    df["cumulative_extra_bn_const"] = df.groupby("scenario")["extra_vs_baseline_bn_const"].cumsum()

    # Confronti con sanità e istruzione a quota di PIL costante
    comps = comparator_shares(cofog)
    for code, (key, _label) in config.COMPARATORS.items():
        _, share = comps[code]
        df[f"{key}_bn"] = share / 100 * df["gdp_bn"]
        df[f"extra_pct_{key}"] = df["extra_vs_baseline_bn"] / df[f"{key}_bn"] * 100
        # "anni di bilancio": somma dei rapporti annui extra_t / bilancio_t
        df[f"extra_years_of_{key}"] = df.groupby("scenario")[f"extra_pct_{key}"].cumsum() / 100

    pop = imf[imf["indicator"] == "LP"].set_index("year")["value"]
    last_pop_year = int(pop.index.max())
    df["population_m"] = df["year"].map(lambda y: float(pop.loc[min(y, last_pop_year)]))
    df["extra_per_capita_eur"] = df["extra_vs_baseline_bn"] * 1e9 / (df["population_m"] * 1e6)
    df["extra_per_capita_eur_const"] = df["extra_per_capita_eur"] / df["price_index"]
    return df


def summary_numbers(scen: pd.DataFrame, gdp: pd.DataFrame, cofog: pd.DataFrame, nato: pd.DataFrame, sipri: pd.DataFrame) -> dict:
    """Numeri chiave usati nel riepilogo Markdown."""
    it_cofog = cofog[(cofog["geo"] == config.FOCUS_COUNTRY)]
    last_cofog_year = int(it_cofog.dropna(subset=["value"])["year"].max())

    def cofog_val(code: str, unit: str) -> float:
        s = it_cofog[(it_cofog["cofog"] == code) & (it_cofog["unit"] == unit) & (it_cofog["year"] == last_cofog_year)]
        return float(s["value"].iloc[0])

    nato_it = nato[(nato["geo"] == config.FOCUS_COUNTRY) & (nato["measure"] == "core_share_gdp")].set_index("year")["value"]
    nato_it_eur = nato[(nato["geo"] == config.FOCUS_COUNTRY) & (nato["measure"] == "core_nat_currency_current_m")].set_index("year")["value"]
    sipri_it = sipri[(sipri["geo"] == config.FOCUS_COUNTRY) & (sipri["measure"] == "share_gdp")].set_index("year")["value"]
    sipri_it_eur = sipri[(sipri["geo"] == config.FOCUS_COUNTRY) & (sipri["measure"] == "local_currency")].set_index("year")["value"]

    g = gdp.set_index("year")
    base_year = int(g[g["source"] == "Eurostat"].index.max())
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    core35 = scen[scen["scenario"] == "core_35"].set_index("year")
    end = config.TARGET_YEAR
    start = config.FIRST_PROJECTION_YEAR

    out: dict = {
        "cofog_year": last_cofog_year,
        "cofog_defence_pct": cofog_val("GF02", "PC_GDP"),
        "cofog_health_pct": cofog_val("GF07", "PC_GDP"),
        "cofog_education_pct": cofog_val("GF09", "PC_GDP"),
        "cofog_social_pct": cofog_val("GF10", "PC_GDP"),
        "cofog_total_pct": cofog_val("TOTAL", "PC_GDP"),
        "cofog_defence_bn": cofog_val("GF02", "MIO_EUR") / 1000,
        "cofog_health_bn": cofog_val("GF07", "MIO_EUR") / 1000,
        "cofog_education_bn": cofog_val("GF09", "MIO_EUR") / 1000,
        "cofog_total_bn": cofog_val("TOTAL", "MIO_EUR") / 1000,
        "nato_share_2024": float(nato_it.loc[2024]),
        "nato_share_2025": float(nato_it.loc[2025]),
        "nato_share_2026": float(nato_it.loc[2026]),
        "nato_eur_2024_bn": float(nato_it_eur.loc[2024]) / 1000,
        "nato_eur_2025_bn": float(nato_it_eur.loc[2025]) / 1000,
        "nato_eur_2026_bn": float(nato_it_eur.loc[2026]) / 1000,
        "sipri_share_2024": float(sipri_it.loc[2024]),
        "sipri_share_2025": float(sipri_it.loc[2025]),
        "sipri_eur_2025_bn": float(sipri_it_eur.loc[2025]) / 1e9,
        # PIL e prezzi
        "price_base_year": base_year,
        "gdp_base_bn": float(g.loc[base_year, "gdp_bn"]),
        "gdp_2035_bn": float(g.loc[end, "gdp_bn"]),
        "gdp_2035_bn_const": float(g.loc[end, "gdp_bn"] / g.loc[end, "price_index"]),
        "price_index_2035": float(g.loc[end, "price_index"]),
        "avg_inflation": float(g.loc[start:end, "inflation"].mean()),
        "avg_real_growth": float(g.loc[start:end, "real_growth"].mean()),
        # Percorso verso il 5%
        "gov_share_2028": float(gov.loc[2028, "total_share"]),
        "gov_total_bn_2026": float(gov.loc[start, "total_bn"]),
        "gov_total_bn_2035": float(gov.loc[end, "total_bn"]),
        "gov_total_bn_2035_const": float(gov.loc[end, "total_bn_const"]),
        "gov_core_bn_2035": float(gov.loc[end, "core_bn"]),
        "gov_extra_2035_bn": float(gov.loc[end, "extra_vs_baseline_bn"]),
        "gov_extra_2035_bn_const": float(gov.loc[end, "extra_vs_baseline_bn_const"]),
        "gov_cumulative_extra_bn": float(gov.loc[end, "cumulative_extra_bn"]),
        "gov_cumulative_extra_bn_const": float(gov.loc[end, "cumulative_extra_bn_const"]),
        "gov_cumulative_total_bn": float(gov["total_bn"].sum()),
        "gov_extra_2035_pct_health": float(gov.loc[end, "extra_pct_sanita"]),
        "gov_extra_2035_pct_education": float(gov.loc[end, "extra_pct_istruzione"]),
        "gov_extra_2035_per_capita": float(gov.loc[end, "extra_per_capita_eur"]),
        "gov_extra_2035_per_capita_const": float(gov.loc[end, "extra_per_capita_eur_const"]),
        "gov_cumulative_extra_years_of_education": float(gov.loc[end, "extra_years_of_istruzione"]),
        "gov_cumulative_extra_years_of_health": float(gov.loc[end, "extra_years_of_sanita"]),
        # Solo core al 3,5% (limite inferiore della nuova spesa)
        "core35_extra_2035_bn": float(core35.loc[end, "extra_vs_baseline_bn"]),
        "core35_extra_2035_bn_const": float(core35.loc[end, "extra_vs_baseline_bn_const"]),
        "core35_cumulative_extra_bn": float(core35.loc[end, "cumulative_extra_bn"]),
        "core35_cumulative_extra_bn_const": float(core35.loc[end, "cumulative_extra_bn_const"]),
        "core35_extra_2035_pct_health": float(core35.loc[end, "extra_pct_sanita"]),
        "core35_extra_2035_pct_education": float(core35.loc[end, "extra_pct_istruzione"]),
        "core35_extra_2035_per_capita": float(core35.loc[end, "extra_per_capita_eur"]),
        "core35_cumulative_extra_years_of_education": float(core35.loc[end, "extra_years_of_istruzione"]),
        "core35_cumulative_extra_years_of_health": float(core35.loc[end, "extra_years_of_sanita"]),
        # Bilanci di confronto nel 2035 (quota costante)
        "health_bn_2035": float(gov.loc[end, "sanita_bn"]),
        "education_bn_2035": float(gov.loc[end, "istruzione_bn"]),
        "baseline_cumulative_total_bn": float(scen[scen["scenario"] == "baseline"]["total_bn"].sum()),
    }
    # Confronto con una base al 2% del PIL (la vecchia soglia NATO), come fa MIL€X
    gdp_proj = g["gdp_bn"].loc[start:end]
    out["two_pct_cumulative_bn"] = float(config.NATO_OLD_FLOOR / 100 * gdp_proj.sum())
    out["gov_extra_vs_2pct_cumulative_bn"] = out["gov_cumulative_total_bn"] - out["two_pct_cumulative_bn"]
    # Peso sulla spesa pubblica totale, a parità di definizione (NATO) e con
    # spesa pubblica totale ipotizzata costante in % del PIL
    out["defence_share_of_public_spending_2025"] = out["nato_share_2025"] / out["cofog_total_pct"] * 100
    out["defence_share_of_public_spending_2035"] = config.NATO_TOTAL_TARGET / out["cofog_total_pct"] * 100
    out["cofog_defence_share_of_public_spending"] = out["cofog_defence_pct"] / out["cofog_total_pct"] * 100
    return out


def run(data: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    gdp = project_gdp(data["gdp"], data["imf"])
    scen = build_scenarios(gdp, data["cofog"], data["imf"])
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    gdp.to_csv(config.DATA_PROCESSED / "italy_gdp_projection.csv", index=False, encoding="utf-8")
    scen.to_csv(config.DATA_PROCESSED / "italy_scenarios.csv", index=False, encoding="utf-8")
    summary = summary_numbers(scen, gdp, data["cofog"], data["nato"], data["sipri"])
    log.info("scenari calcolati: %s", ", ".join(s.key for s in config.SCENARIOS))
    return gdp, scen, summary
