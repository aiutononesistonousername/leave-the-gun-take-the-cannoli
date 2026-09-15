"""Costanti e parametri della pipeline.

Tutti i numeri "di policy" (obiettivi NATO, percorso del governo italiano,
anno di arrivo) vivono qui, così che la metodologia sia leggibile in un solo
posto e modificabile senza toccare il codice di calcolo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Percorsi
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
CHARTS = OUTPUT / "charts"
TABLES = OUTPUT / "tables"

# --------------------------------------------------------------------------
# Fonti
# --------------------------------------------------------------------------
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
# Spesa delle amministrazioni pubbliche per funzione (COFOG), % PIL e milioni di euro
EUROSTAT_COFOG_DATASET = "gov_10a_exp"
# PIL a prezzi correnti, milioni di euro
EUROSTAT_GDP_DATASET = "nama_10_gdp"

# Divisioni COFOG usate nell'analisi (codice -> etichetta italiana)
COFOG_FUNCTIONS: dict[str, str] = {
    "TOTAL": "Spesa pubblica totale",
    "GF01": "Servizi generali",
    "GF02": "Difesa",
    "GF03": "Ordine pubblico e sicurezza",
    "GF04": "Affari economici",
    "GF05": "Protezione dell'ambiente",
    "GF06": "Abitazioni e assetto territoriale",
    "GF07": "Sanità",
    "GF08": "Cultura, ricreazione e religione",
    "GF09": "Istruzione",
    "GF10": "Protezione sociale",
}

# SIPRI Military Expenditure Database (release aprile 2026, dati 1949-2025)
SIPRI_XLSX_URL = "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx"
SIPRI_SHEETS: dict[str, dict] = {
    # nome foglio -> riga di intestazione (0-based), nome misura, moltiplicatore
    "Share of GDP": {"header": 5, "measure": "share_gdp", "scale": 100.0},
    "Constant (2024) US$": {"header": 5, "measure": "usd_2024_m", "scale": 1.0},
    "Current US$": {"header": 5, "measure": "usd_current_m", "scale": 1.0},
    "Local currency calendar years": {"header": 6, "measure": "local_currency", "scale": 1.0},
    "Share of Govt. spending": {"header": 7, "measure": "share_govt", "scale": 100.0},
}

# NATO, Defence Expenditure of NATO Countries (2014-2026), edizione 2026
NATO_XLSX_URL = "https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx"

# IMF World Economic Outlook via DataMapper API
IMF_API = "https://www.imf.org/external/datamapper/api/v1"
IMF_INDICATORS: dict[str, str] = {
    "NGDP_RPCH": "Crescita reale del PIL (%)",
    "PCPIPCH": "Inflazione media (%)",
    "LP": "Popolazione (milioni)",
    "GGXWDG_NGDP": "Debito pubblico lordo (% PIL)",
    "GGXCNL_NGDP": "Indebitamento netto (% PIL)",
    "NGDPD": "PIL a prezzi correnti (miliardi USD)",
}

# --------------------------------------------------------------------------
# Parametri dell'analisi
# --------------------------------------------------------------------------
FOCUS_COUNTRY = "IT"
FIRST_PROJECTION_YEAR = 2026
TARGET_YEAR = 2035

# Impegno NATO, vertice dell'Aia (giugno 2025): 5% del PIL entro il 2035,
# di cui almeno 3,5% per la difesa "core" e fino a 1,5% per spese
# "defence-related" (infrastrutture, cyber, resilienza civile...).
NATO_CORE_TARGET = 3.5
NATO_RELATED_TARGET = 1.5
NATO_TOTAL_TARGET = NATO_CORE_TARGET + NATO_RELATED_TARGET
NATO_OLD_FLOOR = 2.0  # obiettivo del vertice del Galles (2014)

# Punto di partenza 2026 (definizione NATO): ~2,1% core (stima NATO 2026e)
# + ~0,7% di spese "defence-related" rivendicate dal governo = ~2,8%.
# Fonti: NATO (giugno 2026) e Osservatorio MIL€X (luglio 2026).
START_CORE_SHARE = 2.1
START_RELATED_SHARE = 0.7

# Percorso "governativo" ricostruito da MIL€X sui documenti di finanza
# pubblica: circa 3,2% del PIL nel 2028 (+6-7 mld nel 2027, +12-13 mld nel
# 2028), poi crescita lineare fino al 5% nel 2035.
GOV_PATH_WAYPOINTS: dict[int, float] = {2026: 2.8, 2028: 3.2, 2035: 5.0}


@dataclass(frozen=True)
class Scenario:
    """Una traiettoria di spesa in % del PIL (definizione NATO, core + related).

    - ``core_target``: se valorizzato, la quota core sale linearmente fino a
      questo valore nell'anno obiettivo, la quota related resta costante.
    - ``waypoints``: se valorizzati, la quota *totale* segue l'interpolazione
      lineare tra i punti indicati e la quota related sale linearmente fino
      all'obiettivo NATO (1,5%); la quota core è la differenza.
    - senza nessuno dei due: quota costante al livello di partenza.
    """

    key: str
    label: str
    short: str
    description: str
    core_target: float | None = None
    waypoints: dict[int, float] = field(default_factory=dict)


SCENARIOS: list[Scenario] = [
    Scenario(
        key="baseline",
        label="Quota 2026 costante (2,8% del PIL)",
        short="Quota 2026 costante",
        description="Nessun ulteriore aumento in quota di PIL: la spesa resta al 2,8% "
        "(2,1% core + 0,7% related) e cresce in euro solo con il PIL nominale. "
        "È la base rispetto a cui si misura il costo aggiuntivo.",
    ),
    Scenario(
        key="core_35",
        label="Solo core al 3,5% (4,2% totale)",
        short="Core al 3,5%",
        description="La sola difesa core sale linearmente dal 2,1% al 3,5% nel 2035; la componente related resta allo 0,7%.",
        core_target=NATO_CORE_TARGET,
    ),
    Scenario(
        key="gov_path",
        label="Percorso verso il 5% (3,5% + 1,5%)",
        short="Verso il 5%",
        description="Percorso ricostruito da MIL€X: 2,8% nel 2026, circa 3,2% nel 2028, poi crescita lineare fino al 5% del PIL nel 2035.",
        waypoints=GOV_PATH_WAYPOINTS,
    ),
]

# Voci COFOG con cui confrontare la spesa militare aggiuntiva: codice -> (chiave ASCII, etichetta)
COMPARATORS: dict[str, tuple[str, str]] = {"GF07": ("sanita", "Sanità"), "GF09": ("istruzione", "Istruzione")}
