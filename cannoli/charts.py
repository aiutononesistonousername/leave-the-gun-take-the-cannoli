"""Grafici della pipeline (matplotlib, PNG in ``output/charts``).

Regole applicate: un solo asse per grafico, palette categoriale fissa, serie
di contesto in grigio, etichette dirette selettive, griglia recessiva.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter

from . import config, style
from .countries import EU27, name_it
from .report import eu_comparison_table
from .style import AQUA, BLUE, DEEMPHASIS, DEEMPHASIS_DARK, GRID, INK, INK_2, MUTED, ORANGE, SEQUENTIAL, SURFACE, fmt_bn, fmt_num, fmt_pct

log = logging.getLogger(__name__)

CREDIT = "Elaborazione: Leave the gun, take the cannoli"
SOURCE_SIPRI = f"Fonte: SIPRI Military Expenditure Database (aprile 2026). {CREDIT}"
SOURCE_NATO = f"Fonte: NATO, Defence Expenditure of NATO Countries 2014-2026 (giugno 2026); 2025 e 2026 sono stime. {CREDIT}"
SOURCE_COFOG = f"Fonte: Eurostat, gov_10a_exp (spesa delle amministrazioni pubbliche per funzione COFOG). {CREDIT}"
SOURCE_THREE = f"Fonti: NATO (giugno 2026), SIPRI (aprile 2026), Eurostat COFOG. {CREDIT}"
SOURCE_PROJ = (
    f"Fonti: NATO 2026, Eurostat, FMI WEO (aprile 2026), Osservatorio MIL€X. Proiezioni dal 2026 (PIL nominale: crescita reale + inflazione FMI). {CREDIT}"
)

SCENARIO_COLORS = {"baseline": DEEMPHASIS_DARK, "core_35": ORANGE, "gov_path": BLUE}


# --------------------------------------------------------------------------
# Utilità
# --------------------------------------------------------------------------
def _tick_pct(v: float, _pos=None) -> str:
    return f"{v:g}".replace(".", ",") + "%"


def _tick_bn(v: float, _pos=None) -> str:
    return fmt_num(v)


def pct_axis(ax: Axes, axis: str = "y") -> None:
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(FuncFormatter(_tick_pct))


def spread_labels(values: list[float], min_gap: float) -> list[float]:
    """Sposta verticalmente le etichette troppo vicine, preservando l'ordine."""
    order = np.argsort(values)
    out = np.array(values, dtype=float)
    for prev, cur in zip(order, order[1:], strict=False):
        if out[cur] - out[prev] < min_gap:
            out[cur] = out[prev] + min_gap
    return out.tolist()


def horizontal_grid_only(ax: Axes) -> None:
    ax.grid(False, axis="y")
    ax.grid(True, axis="x", color=GRID, linewidth=0.8)
    ax.spines["bottom"].set_visible(False)


def bold_tick(ax: Axes, text: str) -> None:
    for lab in ax.get_yticklabels():
        if lab.get_text() == text:
            lab.set_fontweight("bold")
            lab.set_color(INK)


# --------------------------------------------------------------------------
# 1. Europa: linee 1990-2025 (SIPRI), Italia in evidenza
# --------------------------------------------------------------------------
def chart_europe_lines(sipri: pd.DataFrame) -> Path:
    df = sipri[(sipri["measure"] == "share_gdp") & (sipri["geo"].isin(EU27)) & (sipri["year"] >= 1990)]
    wide = df.pivot(index="year", columns="geo", values="value")
    last = int(wide.index.max())

    fig, ax = style.new_figure(10.5, 6)
    for geo in wide.columns:
        if geo == config.FOCUS_COUNTRY:
            continue
        ax.plot(wide.index, wide[geo], color=DEEMPHASIS, linewidth=1.2, zorder=2)
    ax.plot(wide.index, wide[config.FOCUS_COUNTRY], color=BLUE, linewidth=2.6, zorder=5)

    for y, lab in [
        (config.NATO_OLD_FLOOR, "2% (obiettivo Galles 2014)"),
        (config.NATO_CORE_TARGET, "3,5% core entro il 2035"),
        (config.NATO_TOTAL_TARGET, "5% totale entro il 2035"),
    ]:
        style.hline(ax, y, lab, x_text=1990)

    named = ["IT", "PL", "EL", "DE", "FR", "ES", "LT", "EE"]
    pts = [(g, float(wide.loc[last, g])) for g in named if pd.notna(wide.loc[last, g])]
    ys = spread_labels([p[1] for p in pts], 0.17)
    for (geo, y_true), y_lab in zip(pts, ys, strict=False):
        focus = geo == config.FOCUS_COUNTRY
        ax.plot([last, last + 0.7], [y_true, y_lab], color=BLUE if focus else DEEMPHASIS_DARK, linewidth=0.8, zorder=4)
        style.end_label(ax, last + 0.7, y_lab, f"{name_it(geo)} {fmt_pct(y_true)}", color=INK if focus else INK_2, dx=0.2, weight="bold" if focus else "normal")

    ax.set_xlim(1990, last + 7.5)
    ax.set_ylim(0, max(5.4, float(wide.loc[last].max()) + 0.4))
    ax.set_xticks(range(1990, last + 1, 5))
    pct_axis(ax)
    style.titles(
        fig,
        f"Spesa militare in % del PIL: l'Italia e gli altri paesi dell'UE, 1990-{last}",
        "Definizione SIPRI. In grigio gli altri 26 paesi UE; le linee tratteggiate sono gli obiettivi NATO.",
        SOURCE_SIPRI,
    )
    return style.save(fig, config.CHARTS / "01_europa_spesa_militare_pil.png")


# --------------------------------------------------------------------------
# 2-3. Classifiche a barre (SIPRI 2025 UE27; NATO 2026e alleati europei)
# --------------------------------------------------------------------------
def _ranking(
    df: pd.DataFrame, value_col: str, title: str, subtitle: str, source: str, thresholds: list[tuple[float, str]], filename: str, accent: str = BLUE
) -> Path:
    df = df.sort_values(value_col).reset_index(drop=True)
    fig, ax = style.new_figure(9, 0.3 * len(df) + 1.8)
    colors = [accent if g == config.FOCUS_COUNTRY else DEEMPHASIS for g in df["geo"]]
    ax.barh(df["country"], df[value_col], color=colors, height=0.62, zorder=3)
    horizontal_grid_only(ax)

    mean = float(df[value_col].mean())
    ax.axvline(mean, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
    ax.text(mean, len(df) - 0.1, f" media semplice {fmt_pct(mean)}", color=MUTED, fontsize=8.5, va="bottom", ha="left")
    for x, lab in thresholds:
        ax.axvline(x, color=INK_2, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        ax.text(x, -0.9, f" {lab}", color=INK_2, fontsize=8.5, va="top", ha="left")

    for i, (geo, v) in enumerate(zip(df["geo"], df[value_col], strict=False)):
        if geo == config.FOCUS_COUNTRY or i in (0, len(df) - 1):
            focus = geo == config.FOCUS_COUNTRY
            ax.text(
                v + 0.04,
                i,
                fmt_pct(v, 2 if focus else 1),
                va="center",
                ha="left",
                fontsize=9,
                color=INK if focus else INK_2,
                fontweight="bold" if focus else "normal",
            )
    bold_tick(ax, name_it(config.FOCUS_COUNTRY))
    ax.set_ylim(-1.4, len(df) + 0.6)
    ax.set_xlim(0, float(df[value_col].max()) * 1.12)
    pct_axis(ax, "x")
    style.titles(fig, title, subtitle, source, top=0.905)
    fig.subplots_adjust(left=0.16)
    return style.save(fig, config.CHARTS / filename)


def chart_ranking_sipri(sipri: pd.DataFrame) -> Path:
    year = int(sipri.loc[sipri["measure"] == "share_gdp", "year"].max())
    df = sipri[(sipri["measure"] == "share_gdp") & (sipri["geo"].isin(EU27)) & (sipri["year"] == year)]
    rank = int((df["value"] > float(df.loc[df["geo"] == config.FOCUS_COUNTRY, "value"].iloc[0])).sum()) + 1
    return _ranking(
        df,
        "value",
        f"Spesa militare in % del PIL nei 27 paesi dell'UE, {year}",
        f"Definizione SIPRI. L'Italia è {rank}ª su 27.",
        SOURCE_SIPRI,
        [(config.NATO_OLD_FLOOR, "2%")],
        "02_classifica_ue_sipri.png",
    )


def chart_ranking_nato(nato: pd.DataFrame) -> Path:
    year = int(nato.loc[nato["measure"] == "core_share_gdp", "year"].max())
    europe = [g for g in nato["geo"].unique() if g not in ("US", "CA", "NATO_EUR_CAN", "NATO_TOTAL")]
    df = nato[(nato["measure"] == "core_share_gdp") & (nato["geo"].isin(europe)) & (nato["year"] == year)]
    rank = int((df["value"] > float(df.loc[df["geo"] == config.FOCUS_COUNTRY, "value"].iloc[0])).sum()) + 1
    return _ranking(
        df,
        "value",
        f"Spesa 'core' per la difesa in % del PIL, alleati europei NATO, stima {year}",
        f"Definizione NATO (prezzi 2021). L'Italia è {rank}ª su {len(df)}.",
        SOURCE_NATO,
        [(config.NATO_OLD_FLOOR, "2%"), (config.NATO_CORE_TARGET, "3,5% (2035)")],
        "03_classifica_nato_2026.png",
    )


# --------------------------------------------------------------------------
# 4. Italia: tre definizioni di spesa militare
# --------------------------------------------------------------------------
def chart_three_definitions(cofog: pd.DataFrame, sipri: pd.DataFrame, nato: pd.DataFrame) -> Path:
    it = config.FOCUS_COUNTRY
    n = nato[(nato["geo"] == it) & (nato["measure"] == "core_share_gdp")].set_index("year")["value"].sort_index()
    est_years = set(nato[(nato["geo"] == it) & (nato["measure"] == "core_share_gdp") & (nato["estimate"])]["year"])
    s = sipri[(sipri["geo"] == it) & (sipri["measure"] == "share_gdp")].set_index("year")["value"].sort_index()
    c = cofog[(cofog["geo"] == it) & (cofog["cofog"] == "GF02") & (cofog["unit"] == "PC_GDP")].set_index("year")["value"].sort_index()
    first = int(n.index.min())
    s, c = s[s.index >= first], c[c.index >= first]

    fig, ax = style.new_figure(10.5, 5.8)
    # (etichetta, serie, colore, anni che la fonte stessa marca come stime)
    series = [
        ("NATO, difesa 'core' (base dell'obiettivo 5%)", n, BLUE, est_years),
        ("SIPRI", s, ORANGE, set()),
        ("Eurostat COFOG, funzione 'Difesa'", c, AQUA, set()),
    ]
    ends = []
    for label, ser, col, est_set in series:
        actual = ser[~ser.index.isin(est_set)]
        ax.plot(actual.index, actual.values, color=col, marker="o", markersize=5, label=label, zorder=4)
        est = ser[ser.index.isin(est_set) | (ser.index == actual.index.max())]
        if len(est) > 1:
            ax.plot(est.index, est.values, color=col, linestyle=(0, (3, 2)), marker="o", markersize=5, markerfacecolor=SURFACE, zorder=4)
        ends.append((int(ser.index.max()), float(ser.iloc[-1]), col))
    ys = spread_labels([e[1] for e in ends], 0.09)
    for (x, y, _col), y_lab in zip(ends, ys, strict=False):
        style.end_label(ax, x, y_lab, fmt_pct(y, 2), color=INK_2, dx=0.25)

    jump = float(n.loc[2025] - n.loc[2024])
    ax.annotate(
        f"2025: +{fmt_pct(jump, 2)[:-1]} punti in un anno nella definizione NATO.\n"
        "Secondo Osservatorio CPI e MIL€X circa 0,4 punti sono riclassificazioni\n"
        "di spese già esistenti (pensioni militari, Carabinieri, Guardia di Finanza,\n"
        "Capitanerie di porto, spazio e cyber), non nuova spesa.",
        xy=(2025, float(n.loc[2025])),
        xytext=(2014.2, 2.05),
        fontsize=8.8,
        color=INK_2,
        va="top",
        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8, "shrinkB": 6},
    )
    ax.set_xlim(first - 0.3, int(n.index.max()) + 1.6)
    ax.set_ylim(0.8, 2.6)
    ax.set_xticks(list(range(first, int(n.index.max()) + 1)))
    ax.set_xticklabels([f"{y}" + ("e" if y in est_years else "") for y in range(first, int(n.index.max()) + 1)])
    pct_axis(ax)
    ax.legend(loc="lower right", ncol=1)
    style.titles(
        fig,
        "Quanto spende l'Italia in difesa? Dipende da chi conta",
        "Spesa militare italiana in % del PIL secondo tre definizioni. Tratteggio e cerchi vuoti: stime NATO.",
        SOURCE_THREE,
    )
    return style.save(fig, config.CHARTS / "04_italia_tre_definizioni.png")


# --------------------------------------------------------------------------
# 5. Italia: difesa, sanità e istruzione nel tempo (COFOG)
# --------------------------------------------------------------------------
def chart_italy_cofog(cofog: pd.DataFrame) -> Path:
    it = cofog[cofog["geo"] == config.FOCUS_COUNTRY]
    pct = it[it["unit"] == "PC_GDP"].pivot(index="year", columns="cofog", values="value")
    eur = it[it["unit"] == "MIO_EUR"].pivot(index="year", columns="cofog", values="value")
    share = eur.div(eur["TOTAL"], axis=0) * 100
    items = [("GF07", "Sanità", ORANGE), ("GF09", "Istruzione", AQUA), ("GF02", "Difesa", BLUE)]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.6))
    for ax, data, ttl in [(axes[0], pct, "In % del PIL"), (axes[1], share, "In % della spesa pubblica totale")]:
        last = int(data.dropna(how="all").index.max())
        ends = []
        for code, lab, col in items:
            ser = data[code].dropna()
            ax.plot(ser.index, ser.values, color=col, label=lab, zorder=4)
            ends.append((lab, int(ser.index.max()), float(ser.iloc[-1])))
        gap = 0.28 if data is pct else 0.6
        ys = spread_labels([e[2] for e in ends], gap)
        for (lab, x, y), y_lab in zip(ends, ys, strict=False):
            style.end_label(ax, x, y_lab, f"{lab} {fmt_pct(y)}", color=INK_2, dx=0.4)
        ax.set_title(ttl, loc="left", fontsize=11, fontweight="normal", color=INK_2)
        ax.set_xlim(int(data.index.min()), last + 8)
        ax.set_xticks(list(range(int(data.index.min()), last + 1, 5)))
        ax.set_ylim(0, float(data[[c for c, _, _ in items]].max().max()) * 1.15)
        pct_axis(ax)
    axes[0].legend(loc="upper left", ncol=3)
    style.titles(
        fig,
        "Italia: quanto pesano difesa, sanità e istruzione nei conti pubblici",
        f"Spesa delle amministrazioni pubbliche per funzione (COFOG), {int(pct.index.min())}-{int(pct.dropna(how='all').index.max())}.",
        SOURCE_COFOG,
        top=0.86,
    )
    fig.subplots_adjust(wspace=0.18)
    return style.save(fig, config.CHARTS / "05_italia_difesa_sanita_istruzione.png")


# --------------------------------------------------------------------------
# 6. Confronto UE27: difesa, sanità, istruzione (% PIL, ultimo anno)
# --------------------------------------------------------------------------
def chart_eu_comparison(cofog: pd.DataFrame) -> Path:
    wide = eu_comparison_table(cofog).set_index("geo")
    year = int(wide["anno"].iloc[0])

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 8.6))
    for ax, (code, lab, col) in zip(
        axes, [("difesa_pct_pil", "Difesa", BLUE), ("sanita_pct_pil", "Sanità", ORANGE), ("istruzione_pct_pil", "Istruzione", AQUA)], strict=False
    ):
        ser = wide[code].dropna().sort_values()
        colors = [col if g == config.FOCUS_COUNTRY else DEEMPHASIS for g in ser.index]
        ax.barh([name_it(g) for g in ser.index], ser.values, color=colors, height=0.62, zorder=3)
        horizontal_grid_only(ax)
        mean = float(ser.mean())
        ax.axvline(mean, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        ax.text(mean, len(ser) - 0.1, f" media {fmt_pct(mean)}", color=MUTED, fontsize=8.5, va="bottom", ha="left")
        it_val = float(ser.loc[config.FOCUS_COUNTRY])
        rank = int((ser > it_val).sum()) + 1
        i = list(ser.index).index(config.FOCUS_COUNTRY)
        ax.text(it_val + ser.max() * 0.02, i, fmt_pct(it_val), va="center", ha="left", fontsize=9, color=INK, fontweight="bold")
        ax.set_title(f"{lab}: Italia {rank}ª su {len(ser)}", loc="left", fontsize=11, color=INK, pad=14)
        ax.set_xlim(0, float(ser.max()) * 1.18)
        ax.set_ylim(-0.7, len(ser) + 0.7)
        ax.tick_params(axis="y", labelsize=8.5)
        bold_tick(ax, name_it(config.FOCUS_COUNTRY))
        pct_axis(ax, "x")
    style.titles(
        fig,
        f"Difesa, sanità e istruzione in % del PIL nei 27 paesi dell'UE, {year}",
        "Stessa definizione per tutti (Eurostat COFOG). L'Italia spende meno della media UE in sanità e istruzione.",
        SOURCE_COFOG,
        top=0.86,
    )
    fig.subplots_adjust(wspace=0.55, left=0.09)
    return style.save(fig, config.CHARTS / "06_confronto_ue27_difesa_sanita_istruzione.png")


# --------------------------------------------------------------------------
# 7. Scenari 2026-2035 (quota del PIL e miliardi di euro)
# --------------------------------------------------------------------------
def chart_scenarios(scen: pd.DataFrame, nato: pd.DataFrame) -> Path:
    it = config.FOCUS_COUNTRY
    hist_share = nato[(nato["geo"] == it) & (nato["measure"] == "core_share_gdp")].set_index("year")["value"].sort_index()
    hist_eur = nato[(nato["geo"] == it) & (nato["measure"] == "core_nat_currency_current_m")].set_index("year")["value"].sort_index() / 1000
    est_years = set(nato[(nato["geo"] == it) & (nato["estimate"]) & (nato["measure"] == "core_share_gdp")]["year"])
    start, end = config.FIRST_PROJECTION_YEAR, config.TARGET_YEAR

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6))
    panels = [
        (axes[0], "total_share", hist_share, lambda v: fmt_pct(v), "Quota del PIL (definizione NATO: core + related)"),
        (axes[1], "total_bn", hist_eur, lambda v: fmt_bn(v), "Miliardi di euro a prezzi correnti"),
    ]
    for ax, col, hist, fmt, ttl in panels:
        ax.axvspan(start, end, color=GRID, alpha=0.45, linewidth=0, zorder=0)
        actual = hist[~hist.index.isin(est_years)]
        est = hist[hist.index.isin(est_years) | (hist.index == actual.index.max())]
        ax.plot(actual.index, actual.values, color=INK, label="Storico NATO (solo core)", zorder=4)
        ax.plot(est.index, est.values, color=INK, linestyle=(0, (3, 2)), zorder=4)
        ends = []
        for s in config.SCENARIOS:
            d = scen[scen["scenario"] == s.key]
            ax.plot(d["year"], d[col], color=SCENARIO_COLORS[s.key], linewidth=2.4 if s.key == "gov_path" else 2, label=s.label, zorder=5)
            ends.append((float(d[col].iloc[-1]), fmt(float(d[col].iloc[-1]))))
        ax.set_xlim(int(hist.index.min()), end + 3.6)
        if col == "total_share":
            g = scen[scen["scenario"] == "gov_path"]
            ax.plot(g["year"], g["core_share"], color=BLUE, linewidth=1.2, linestyle=(0, (2, 2)), label="di cui core (percorso 5%)", zorder=5)
            ends.append((float(g["core_share"].iloc[-1]), f"core {fmt_pct(float(g['core_share'].iloc[-1]))}"))
            ax.set_ylim(0, 6.2)
            for y, lab, x_text in [(config.NATO_OLD_FLOOR, "2%", 2014), (config.NATO_CORE_TARGET, "3,5%", 2014), (config.NATO_TOTAL_TARGET, "5%", start + 0.2)]:
                style.hline(ax, y, lab, x_text=x_text, x_max=end)
            ax.annotate(
                "dal 2026 il governo conteggia\nanche ~0,7% di spese 'related'",
                xy=(start, float(hist.loc[start]) + 0.35),
                xytext=(2015.5, 3.05),
                fontsize=8.8,
                color=INK_2,
                va="top",
                arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8},
            )
        else:
            ax.set_ylim(0, None)
        gap = 0.2 if col == "total_share" else 6
        ys = spread_labels([e[0] for e in ends], gap)
        for (_y, text), y_lab in zip(ends, ys, strict=False):
            style.end_label(ax, end, y_lab, text, color=INK_2, dx=0.2)
        ax.set_title(ttl, loc="left", fontsize=11, fontweight="normal", color=INK_2)
        ax.set_xticks(list(range(int(hist.index.min()), end + 1, 3)))
        ax.text(start + 0.2, ax.get_ylim()[1] * 0.985, "proiezione", fontsize=8.5, color=MUTED, va="top")
    pct_axis(axes[0])
    axes[1].yaxis.set_major_formatter(FuncFormatter(_tick_bn))
    axes[0].legend(loc="upper left", fontsize=8.5, frameon=True, facecolor=SURFACE, edgecolor="none", framealpha=1)
    style.titles(
        fig,
        "Italia: tre traiettorie della spesa militare fino al 2035",
        "Storico NATO (core) e scenari a partire dal 2026. Il percorso verso il 5% è quello ricostruito da MIL€X sui documenti di finanza pubblica.",
        SOURCE_PROJ,
        top=0.86,
    )
    fig.subplots_adjust(wspace=0.2)
    return style.save(fig, config.CHARTS / "07_scenari_2035.png")


# --------------------------------------------------------------------------
# 8. Costo aggiuntivo annuo e cumulato
# --------------------------------------------------------------------------
def chart_extra_cost(scen: pd.DataFrame) -> Path:
    start, end = config.FIRST_PROJECTION_YEAR + 1, config.TARGET_YEAR
    years = list(range(start, end + 1))
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    c35 = scen[scen["scenario"] == "core_35"].set_index("year")
    labels = {s.key: s.label for s in config.SCENARIOS}

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    x = np.arange(len(years))
    w = 0.3
    axes[0].bar(x - w / 2 - 0.02, gov.loc[years, "extra_vs_baseline_bn"], w, color=BLUE, label=labels["gov_path"], zorder=3)
    axes[0].bar(x + w / 2 + 0.02, c35.loc[years, "extra_vs_baseline_bn"], w, color=ORANGE, label=labels["core_35"], zorder=3)
    for dx, d, _col in [(-w / 2 - 0.02, gov, BLUE), (w / 2 + 0.02, c35, ORANGE)]:
        v = float(d.loc[end, "extra_vs_baseline_bn"])
        axes[0].text(x[-1] + dx, v + 1, fmt_num(v), ha="center", va="bottom", fontsize=9, color=INK)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(years)
    axes[0].set_title("Spesa aggiuntiva per anno rispetto al livello 2026 (mld €)", loc="left", fontsize=11, fontweight="normal", color=INK_2)
    axes[0].legend(loc="upper left", fontsize=8.5)

    for d, col in [(gov, BLUE), (c35, ORANGE)]:
        ser = d.loc[config.FIRST_PROJECTION_YEAR : end, "cumulative_extra_bn"]
        axes[1].plot(ser.index, ser.values, color=col, zorder=4)
        axes[1].fill_between(ser.index, 0, ser.values, color=col, alpha=0.08, linewidth=0)
        style.end_label(axes[1], end, float(ser.iloc[-1]), fmt_bn(float(ser.iloc[-1])), color=INK_2, dx=0.15)
    axes[1].set_title("Spesa aggiuntiva cumulata 2026-2035 (mld €)", loc="left", fontsize=11, fontweight="normal", color=INK_2)
    axes[1].set_xlim(config.FIRST_PROJECTION_YEAR, end + 1.8)
    axes[1].set_ylim(0, None)
    axes[1].set_xticks(list(range(config.FIRST_PROJECTION_YEAR, end + 1)))
    for ax in axes:
        ax.yaxis.set_major_formatter(FuncFormatter(_tick_bn))
    style.titles(
        fig,
        "Quanto costa in più arrivare al 5%",
        "Differenza rispetto allo scenario a quota 2026 costante (2,8% del PIL), a prezzi correnti.",
        SOURCE_PROJ,
        top=0.86,
    )
    fig.subplots_adjust(wspace=0.18)
    return style.save(fig, config.CHARTS / "08_costo_aggiuntivo.png")


# --------------------------------------------------------------------------
# 9. Extra-spesa in rapporto ai bilanci di sanità e istruzione
# --------------------------------------------------------------------------
def chart_extra_vs_budgets(scen: pd.DataFrame, summary: dict) -> Path:
    gov = scen[scen["scenario"] == "gov_path"].set_index("year")
    years = list(range(config.FIRST_PROJECTION_YEAR + 1, config.TARGET_YEAR + 1))
    fig, ax = style.new_figure(10.5, 5.6)
    for col, lab, color in [
        ("extra_pct_sanita", "in % del bilancio della sanità", ORANGE),
        ("extra_pct_istruzione", "in % del bilancio dell'istruzione", AQUA),
    ]:
        ser = gov.loc[years, col]
        ax.plot(ser.index, ser.values, color=color, marker="o", markersize=5, label=lab, zorder=4)
        style.end_label(ax, config.TARGET_YEAR, float(ser.iloc[-1]), fmt_pct(float(ser.iloc[-1]), 0), color=INK_2, dx=0.15)
    ax.set_xlim(years[0] - 0.3, config.TARGET_YEAR + 1.2)
    ax.set_ylim(0, None)
    ax.set_xticks(years)
    pct_axis(ax)
    ax.legend(loc="upper left")
    h = summary["health_bn_2035"]
    e = summary["education_bn_2035"]
    ax.text(
        years[0],
        ax.get_ylim()[1] * 0.78,
        f"Nel 2035 l'aumento vale {fmt_bn(summary['gov_extra_2035_bn'])} a prezzi correnti "
        f"({fmt_bn(summary['gov_extra_2035_bn_const'])} a prezzi {summary['price_base_year']}),\n"
        f"su un bilancio proiettato di {fmt_bn(h)} per la sanità e {fmt_bn(e)} per l'istruzione\n"
        "(entrambi a quota di PIL costante). Con il solo core al 3,5% l'aumento sarebbe\n"
        f"{fmt_bn(summary['core35_extra_2035_bn'])}, cioè il {fmt_pct(summary['core35_extra_2035_pct_health'], 0)} della sanità "
        f"e il {fmt_pct(summary['core35_extra_2035_pct_education'], 0)} dell'istruzione.",
        fontsize=9,
        color=INK_2,
        va="top",
    )
    style.titles(
        fig,
        "Nel 2035 l'aumento della spesa per la difesa varrà un terzo della sanità e metà dell'istruzione",
        "Spesa aggiuntiva annua del percorso verso il 5% rispetto alla quota 2026, in rapporto ai bilanci pubblici di sanità e istruzione (stesso anno).",
        SOURCE_PROJ,
    )
    return style.save(fig, config.CHARTS / "09_extra_vs_sanita_istruzione.png")


# --------------------------------------------------------------------------
# 10. Oggi e nel 2035: difesa, sanità, istruzione (dumbbell)
# --------------------------------------------------------------------------
def chart_dumbbell(summary: dict) -> Path:
    """Oggi e nel 2035: difesa (NATO 2025 -> core 3,5% e totale 5%), sanità e istruzione (COFOG, costanti)."""
    rows = [
        ("Difesa (definizione NATO)", summary["nato_share_2025"], config.NATO_CORE_TARGET, config.NATO_TOTAL_TARGET),
        ("Istruzione (COFOG)", summary["cofog_education_pct"], None, summary["cofog_education_pct"]),
        ("Sanità (COFOG)", summary["cofog_health_pct"], None, summary["cofog_health_pct"]),
    ]
    fig, ax = style.new_figure(10, 4.4)
    light, mid, dark = SEQUENTIAL[1], SEQUENTIAL[3], SEQUENTIAL[6]
    for i, (_lab, a, core, total) in enumerate(rows):
        ax.plot([a, total], [i, i], color=DEEMPHASIS_DARK, linewidth=2.5, zorder=2)
        ax.scatter([a], [i], color=light, s=110, zorder=4, edgecolor=SURFACE, linewidth=1.5)
        if core is not None:
            ax.scatter([core], [i], color=mid, s=110, zorder=5, edgecolor=SURFACE, linewidth=1.5)
            ax.text(core, i + 0.28, f"core {fmt_pct(core)}", ha="center", va="bottom", fontsize=9, color=INK_2)
        ax.scatter([total], [i], color=dark, s=110, zorder=6, edgecolor=SURFACE, linewidth=1.5)
        if abs(total - a) > 0.05:
            ax.text(a - 0.12, i, fmt_pct(a, 2), ha="right", va="center", fontsize=9.5, color=INK_2)
            ax.text(total + 0.12, i, f"totale {fmt_pct(total)}", ha="left", va="center", fontsize=9.5, color=INK, fontweight="bold")
        else:
            ax.text(total + 0.12, i, f"{fmt_pct(total)} (quota costante per ipotesi)", ha="left", va="center", fontsize=9.5, color=INK_2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=10, color=INK)
    ax.set_ylim(-0.7, len(rows) - 0.2)
    ax.set_xlim(0, 8.4)
    horizontal_grid_only(ax)
    pct_axis(ax, "x")
    ax.scatter([], [], color=light, s=80, label="2025 (NATO) / 2024 (COFOG)")
    ax.scatter([], [], color=mid, s=80, label="2035, core 3,5%")
    ax.scatter([], [], color=dark, s=80, label="2035, totale 5%")
    ax.legend(loc="lower right", ncol=3)
    style.titles(
        fig,
        "Nel 2035 la spesa per la difesa supererà quella per l'istruzione",
        "In % del PIL. Le definizioni non coincidono: quella NATO include pensioni militari e parte delle forze di polizia, che nel COFOG stanno altrove.",
        SOURCE_PROJ,
        top=0.84,
    )
    return style.save(fig, config.CHARTS / "10_difesa_supera_istruzione.png")


# --------------------------------------------------------------------------
# Regia
# --------------------------------------------------------------------------
def render_all(data: dict[str, pd.DataFrame], scen: pd.DataFrame, summary: dict) -> dict[str, Path]:
    style.apply_style()
    config.CHARTS.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    outputs["europe_lines"] = chart_europe_lines(data["sipri"])
    outputs["ranking_sipri"] = chart_ranking_sipri(data["sipri"])
    outputs["ranking_nato"] = chart_ranking_nato(data["nato"])
    outputs["three_definitions"] = chart_three_definitions(data["cofog"], data["sipri"], data["nato"])
    outputs["italy_cofog"] = chart_italy_cofog(data["cofog"])
    outputs["eu_comparison"] = chart_eu_comparison(data["cofog"])
    outputs["scenarios"] = chart_scenarios(scen, data["nato"])
    outputs["extra_cost"] = chart_extra_cost(scen)
    outputs["extra_vs_budgets"] = chart_extra_vs_budgets(scen, summary)
    outputs["dumbbell"] = chart_dumbbell(summary)
    for path in outputs.values():
        log.info("grafico: %s", path.name)
    return outputs
