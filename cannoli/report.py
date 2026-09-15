"""Tabelle CSV e riepilogo Markdown dei risultati (``output/``)."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from . import config
from .countries import EU27, name_it
from .style import fmt_bn, fmt_num, fmt_pct

log = logging.getLogger(__name__)


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    return "\n".join(lines)


def eu_comparison_table(cofog: pd.DataFrame) -> pd.DataFrame:
    """Difesa, sanità e istruzione in % del PIL per i 27 paesi UE nell'ultimo anno
    in cui almeno 25 paesi hanno dati."""
    codes = {"GF02": "difesa_pct_pil", "GF07": "sanita_pct_pil", "GF09": "istruzione_pct_pil"}
    df = cofog[(cofog["unit"] == "PC_GDP") & (cofog["geo"].isin(EU27)) & (cofog["cofog"].isin(codes))]
    counts = df.dropna(subset=["value"]).groupby("year")["geo"].nunique()
    year = int(counts[counts >= 25].index.max())
    wide = df[df["year"] == year].pivot(index="geo", columns="cofog", values="value").rename(columns=codes)
    wide.insert(0, "country", [name_it(g) for g in wide.index])
    wide.insert(0, "anno", year)
    return wide.reset_index()


def write_tables(data: dict[str, pd.DataFrame], scen: pd.DataFrame) -> dict[str, pd.DataFrame]:
    config.TABLES.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}
    eu_table = eu_comparison_table(data["cofog"])

    # Scenari: una riga per anno, colonne per scenario
    values = ["total_share", "total_bn", "total_bn_const", "extra_vs_baseline_bn", "cumulative_extra_bn", "cumulative_extra_bn_const"]
    wide = scen.pivot(index="year", columns="scenario", values=values)
    wide.columns = [f"{a}__{b}" for a, b in wide.columns]
    wide = wide.reset_index().rename(columns={"year": "anno"})
    base = scen[scen["scenario"] == "baseline"].set_index("year")
    wide.insert(1, "pil_mld_eur", base["gdp_bn"].round(1).values)
    wide.insert(2, "indice_prezzi", base["price_index"].round(4).values)
    tables["scenari"] = wide.round(2)

    # Tre definizioni per l'Italia
    it = config.FOCUS_COUNTRY
    n = data["nato"][(data["nato"]["geo"] == it) & (data["nato"]["measure"] == "core_share_gdp")].set_index("year")["value"]
    s = data["sipri"][(data["sipri"]["geo"] == it) & (data["sipri"]["measure"] == "share_gdp")].set_index("year")["value"]
    c = data["cofog"][(data["cofog"]["geo"] == it) & (data["cofog"]["cofog"] == "GF02") & (data["cofog"]["unit"] == "PC_GDP")].set_index("year")["value"]
    three = pd.DataFrame({"nato_core_pct_pil": n, "sipri_pct_pil": s, "eurostat_cofog_pct_pil": c}).loc[2014:].round(2)
    tables["italia_tre_definizioni"] = three.reset_index().rename(columns={"year": "anno"})

    # Classifica SIPRI ultimo anno, UE27
    sp = data["sipri"]
    year = int(sp.loc[sp["measure"] == "share_gdp", "year"].max())
    rank = sp[(sp["measure"] == "share_gdp") & (sp["geo"].isin(EU27)) & (sp["year"] == year)].sort_values("value", ascending=False)
    rank = rank[["geo", "country", "value"]].rename(columns={"value": f"sipri_pct_pil_{year}"}).reset_index(drop=True)
    rank.insert(0, "posizione", range(1, len(rank) + 1))
    tables[f"classifica_ue27_sipri_{year}"] = rank.round(2)

    # Confronto UE27 COFOG
    tables["ue27_cofog_difesa_sanita_istruzione"] = eu_table.sort_values("difesa_pct_pil", ascending=False).reset_index(drop=True)

    for name, df in tables.items():
        out = config.TABLES / f"{name}.csv"
        df.to_csv(out, index=False, encoding="utf-8")
        log.info("tabella: %s", out.name)
    return tables


def write_summary(summary: dict, scen: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> str:
    s = summary
    year = s["cofog_year"]
    py = s["price_base_year"]
    labels = {sc.key: sc.label for sc in config.SCENARIOS}
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    end = config.TARGET_YEAR

    lines = [
        "# Riepilogo dei risultati",
        "",
        f"_Generato automaticamente il {date.today().isoformat()} da `python main.py`._",
        "",
        "## Punto di partenza",
        "",
        f"- Spesa pubblica italiana {year} (Eurostat COFOG, % del PIL): difesa {fmt_pct(s['cofog_defence_pct'])}, "
        f"sanità {fmt_pct(s['cofog_health_pct'])}, istruzione {fmt_pct(s['cofog_education_pct'])}, "
        f"protezione sociale {fmt_pct(s['cofog_social_pct'])}, totale {fmt_pct(s['cofog_total_pct'])}.",
        f"- In euro ({year}): difesa {fmt_bn(s['cofog_defence_bn'], 1)}, sanità {fmt_bn(s['cofog_health_bn'], 1)}, "
        f"istruzione {fmt_bn(s['cofog_education_bn'], 1)}, spesa pubblica totale {fmt_bn(s['cofog_total_bn'], 0)}.",
        f"- Spesa per la difesa secondo la NATO (core): {fmt_pct(s['nato_share_2024'], 2)} nel 2024 ({fmt_bn(s['nato_eur_2024_bn'], 1)}), "
        f"{fmt_pct(s['nato_share_2025'], 2)} nel 2025 ({fmt_bn(s['nato_eur_2025_bn'], 1)}), "
        f"{fmt_pct(s['nato_share_2026'], 2)} stimato nel 2026 ({fmt_bn(s['nato_eur_2026_bn'], 1)}).",
        f"- Spesa militare secondo SIPRI: {fmt_pct(s['sipri_share_2024'], 2)} nel 2024, {fmt_pct(s['sipri_share_2025'], 2)} nel 2025 ({fmt_bn(s['sipri_eur_2025_bn'], 1)}).",
        f"- Peso sulla spesa pubblica totale, a parità di definizione NATO e con spesa pubblica costante al {fmt_pct(s['cofog_total_pct'])} del PIL: "
        f"{fmt_pct(s['defence_share_of_public_spending_2025'])} nel 2025 (2,09%), circa {fmt_pct(s['defence_share_of_public_spending_2035'])} al 5%. "
        f"Nella definizione COFOG la difesa vale oggi il {fmt_pct(s['cofog_defence_share_of_public_spending'])} della spesa pubblica.",
        "",
        "## Ipotesi macro",
        "",
        f"- PIL nominale: {fmt_bn(s['gdp_base_bn'])} nel {py} (Eurostat) -> {fmt_bn(s['gdp_2035_bn'])} nel {end} a prezzi correnti, "
        f"pari a {fmt_bn(s['gdp_2035_bn_const'])} a prezzi {py}.",
        f"- Crescita reale media {config.FIRST_PROJECTION_YEAR}-{end}: {fmt_pct(s['avg_real_growth'], 1)} l'anno; inflazione media: {fmt_pct(s['avg_inflation'], 1)} l'anno "
        f"(FMI WEO fino al 2031, poi costanti). L'indice dei prezzi {end} vale {fmt_num(s['price_index_2035'], 3)} (base {py} = 1).",
        "- Gli importi in euro sono a prezzi correnti salvo dove indicato 'a prezzi "
        f"{py}'; i rapporti (in % di un bilancio, anni di bilancio, quote di PIL) non dipendono dall'inflazione.",
        "",
        "## Proiezione 2026-2035",
        "",
        f"- Percorso verso il 5%: {fmt_pct(config.GOV_PATH_WAYPOINTS[2026])} nel 2026, {fmt_pct(s['gov_share_2028'])} nel 2028, 5% nel {end}.",
        f"- Spesa per la difesa nel {end} al 5% (definizione NATO allargata, core + related): **{fmt_bn(s['gov_total_bn_2035'])}** all'anno a prezzi correnti "
        f"({fmt_bn(s['gov_total_bn_2035_const'])} a prezzi {py}), di cui core {fmt_bn(s['gov_core_bn_2035'])}; nel 2026 sono {fmt_bn(s['gov_total_bn_2026'])}.",
        f"- Costo aggiuntivo nel solo {end} rispetto alla quota 2026: tra **{fmt_bn(s['core35_extra_2035_bn'])}** (solo core al 3,5%) e "
        f"**{fmt_bn(s['gov_extra_2035_bn'])}** (5%), cioè tra {fmt_bn(s['core35_extra_2035_bn_const'])} e {fmt_bn(s['gov_extra_2035_bn_const'])} a prezzi {py}.",
        f"- In rapporto ai bilanci {end} a quota di PIL costante (sanità {fmt_bn(s['health_bn_2035'])}, istruzione {fmt_bn(s['education_bn_2035'])}): "
        f"tra il {fmt_pct(s['core35_extra_2035_pct_health'], 0)} e il {fmt_pct(s['gov_extra_2035_pct_health'], 0)} della sanità, "
        f"tra il {fmt_pct(s['core35_extra_2035_pct_education'], 0)} e il {fmt_pct(s['gov_extra_2035_pct_education'], 0)} dell'istruzione; "
        f"per abitante tra {fmt_num(s['core35_extra_2035_per_capita'])} e {fmt_num(s['gov_extra_2035_per_capita'])} € "
        f"({fmt_num(s['gov_extra_2035_per_capita_const'])} € a prezzi {py} nello scenario 5%).",
        f"- Costo aggiuntivo cumulato {config.FIRST_PROJECTION_YEAR}-{end}: tra **{fmt_bn(s['core35_cumulative_extra_bn'])}** e **{fmt_bn(s['gov_cumulative_extra_bn'])}** a prezzi correnti "
        f"(tra {fmt_bn(s['core35_cumulative_extra_bn_const'])} e {fmt_bn(s['gov_cumulative_extra_bn_const'])} a prezzi {py}). "
        f"Sommando i rapporti annui, equivale a {fmt_num(s['core35_cumulative_extra_years_of_education'], 1)}-{fmt_num(s['gov_cumulative_extra_years_of_education'], 1)} anni di spesa per l'istruzione "
        f"o {fmt_num(s['core35_cumulative_extra_years_of_health'], 1)}-{fmt_num(s['gov_cumulative_extra_years_of_health'], 1)} anni di spesa sanitaria.",
        f"- Spesa cumulata {config.FIRST_PROJECTION_YEAR}-{end} lungo il percorso al 5%: {fmt_bn(s['gov_cumulative_total_bn'])}; "
        f"rispetto a una base al 2% del PIL ({fmt_bn(s['two_pct_cumulative_bn'])}) la differenza è {fmt_bn(s['gov_extra_vs_2pct_cumulative_bn'])} "
        "(MIL€X, luglio 2026, stima 498 mld € sull'orizzonte 2025-2035 con le previsioni di PIL del DFP).",
        "",
        "## Scenari, anno per anno",
        "",
    ]
    base = scen[scen["scenario"] == "baseline"].set_index("year")
    c35 = scen[scen["scenario"] == "core_35"].set_index("year")
    table = pd.DataFrame(
        {
            "Anno": gov.index,
            "PIL (mld €)": gov["gdp_bn"].round(0).map(fmt_num),
            "Indice prezzi": gov["price_index"].map(lambda v: fmt_num(v, 3)),
            f"{labels['baseline']}: mld €": base["total_bn"].map(lambda v: fmt_num(v, 1)),
            f"{labels['core_35']}: mld €": c35["total_bn"].map(lambda v: fmt_num(v, 1)),
            "Verso il 5%: quota": gov["total_share"].map(lambda v: fmt_pct(v, 2)),
            "Verso il 5%: mld €": gov["total_bn"].map(lambda v: fmt_num(v, 1)),
            "Extra vs quota 2026 (mld €)": gov["extra_vs_baseline_bn"].map(lambda v: fmt_num(v, 1)),
            "Extra cumulato (mld €)": gov["cumulative_extra_bn"].map(lambda v: fmt_num(v, 1)),
            f"Extra cumulato a prezzi {py} (mld €)": gov["cumulative_extra_bn_const"].map(lambda v: fmt_num(v, 1)),
        }
    )
    lines.append(_md_table(table))
    lines += ["", "## Tre definizioni della spesa militare italiana (% del PIL)", ""]
    three = tables["italia_tre_definizioni"].copy()
    three.columns = ["Anno", "NATO (core)", "SIPRI", "Eurostat COFOG"]
    for col in three.columns[1:]:
        three[col] = three[col].map(lambda v: "" if pd.isna(v) else fmt_pct(v, 2))
    lines.append(_md_table(three))
    lines += ["", "## Ipotesi e limiti", ""]
    lines += [
        "- Il 5% è misurato dalla NATO sul PIL a prezzi 2021; qui la quota è applicata al PIL nominale proiettato. Per un rapporto la scelta della base dei prezzi è quasi ininfluente.",
        f"- L'inflazione al consumo (FMI) è usata come deflatore sia per costruire il PIL nominale sia per esprimere gli importi a prezzi {py}: è un'approssimazione del deflatore del PIL.",
        "- Sanità e istruzione sono proiettate a quota di PIL costante (ultimo dato Eurostat): è uno scenario 'a politiche invariate', non una previsione. I documenti di finanza pubblica prevedono per la sanità una quota in lieve calo, il che renderebbe i rapporti più alti.",
        "- La quota 2026 (2,8%) include 0,7 punti di spese 'defence-related' rivendicate dal governo ma non certificate dalla NATO. Lo scenario 'solo core al 3,5%' è il limite inferiore della nuova spesa; il percorso al 5% il limite superiore, perché parte della componente related potrebbe essere riclassificazione di spese esistenti.",
        "- Il percorso 2,8% -> 3,2% (2028) -> 5% (2035) è quello ricostruito da MIL€X; il governo non ha pubblicato una traiettoria ufficiale anno per anno.",
        "- Le definizioni NATO e COFOG non coincidono (pensioni militari e parte delle forze di polizia sono 'difesa' per la NATO ma 'protezione sociale' e 'ordine pubblico' nel COFOG): i confronti fra difesa NATO e sanità/istruzione COFOG vanno letti come ordini di grandezza.",
        "- Il modello misura il costo, non le coperture: nessuna ipotesi su debito, tagli o entrate.",
    ]
    text = "\n".join(lines) + "\n"
    out = config.OUTPUT / "summary.md"
    out.write_text(text, encoding="utf-8")
    log.info("riepilogo: %s", out.name)
    return text
