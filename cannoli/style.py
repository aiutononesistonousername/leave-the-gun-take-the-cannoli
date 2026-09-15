"""Stile grafico condiviso (matplotlib).

Palette categoriale validata per la leggibilità con daltonismo (deuteranopia,
protanopia, tritanopia) e per il contrasto sulla superficie chiara; segni
sottili, griglia recessiva, etichette dirette selettive.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

matplotlib.use("Agg")

# Palette categoriale (ordine fisso: un colore segue l'entità, non il rango)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE, ORANGE, AQUA, YELLOW = SERIES[:4]

# Superficie e inchiostri
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
DEEMPHASIS = "#c9c8c1"  # serie di contesto (gli "altri paesi")
DEEMPHASIS_DARK = "#a6a49d"

# Sequenziale (blu chiaro -> scuro), per magnitudini
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

FONT_STACK = ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"]


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": FONT_STACK,
            "font.size": 10,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "axes.axisbelow": True,
            "axes.titlelocation": "left",
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.titlecolor": INK,
            "axes.labelcolor": INK_2,
            "axes.labelsize": 9.5,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "lines.linewidth": 2,
            "lines.solid_joinstyle": "round",
            "lines.solid_capstyle": "round",
            "legend.frameon": False,
            "legend.fontsize": 9,
            "legend.labelcolor": INK_2,
            "figure.dpi": 100,
            "savefig.dpi": 160,
        }
    )


def new_figure(width: float = 10, height: float = 5.6, **kwargs) -> tuple[Figure, Axes]:
    fig, ax = plt.subplots(figsize=(width, height), **kwargs)
    return fig, ax


def titles(fig: Figure, title: str, subtitle: str | None = None, source: str | None = None, top: float = 0.90) -> None:
    """Titolo (grassetto), sottotitolo (inchiostro secondario) e fonte a piè di figura.

    Le posizioni verticali sono calcolate in pollici dal bordo, così restano
    corrette anche nelle figure basse.
    """
    height = fig.get_size_inches()[1]
    fig.text(0.01, 1 - 0.12 / height, title, ha="left", va="top", fontsize=14, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.01, 1 - 0.40 / height, subtitle, ha="left", va="top", fontsize=10, color=INK_2)
    if source:
        fig.text(0.01, 0.06 / height, source, ha="left", va="bottom", fontsize=8, color=MUTED)
    fig.subplots_adjust(top=min(top, 1 - 0.75 / height), bottom=0.12, left=0.07, right=0.97)


def hline(ax: Axes, y: float, label: str, color: str = MUTED, x_text: float | None = None, x_max: float | None = None) -> None:
    """Linea orizzontale di riferimento (soglia) con etichetta discreta.

    Con ``x_max`` la linea si ferma prima del bordo destro, lasciando spazio
    alle etichette di fine serie.
    """
    if x_max is None:
        ax.axhline(y, color=color, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    else:
        ax.plot([ax.get_xlim()[0], x_max], [y, y], color=color, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    x = ax.get_xlim()[0] if x_text is None else x_text
    ax.text(x, y, f" {label}", ha="left", va="bottom", fontsize=8.5, color=color)


def end_label(ax: Axes, x: float, y: float, text: str, color: str = INK_2, dx: float = 0.3, fontsize: float = 9, weight: str = "normal") -> None:
    ax.text(x + dx, y, text, ha="left", va="center", fontsize=fontsize, color=color, fontweight=weight)


def save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return path


def fmt_pct(v: float, decimals: int = 1) -> str:
    """Formato italiano: virgola decimale, simbolo %."""
    return f"{v:.{decimals}f}".replace(".", ",") + "%"


def fmt_bn(v: float, decimals: int = 0) -> str:
    return f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mld €"


def fmt_num(v: float, decimals: int = 0) -> str:
    return f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
