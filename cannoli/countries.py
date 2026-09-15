"""Anagrafica dei paesi: allinea i codici Eurostat con i nomi usati da SIPRI e NATO.

Ogni fonte chiama i paesi in modo diverso (Eurostat usa codici a due lettere
con "EL" per la Grecia, SIPRI "Czechia" e "Türkiye", NATO "Slovak Republic").
Questa tabella è l'unico punto di raccordo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    geo: str  # codice Eurostat (ISO 3166-1 alpha-2, con EL/UK)
    iso3: str
    name_en: str
    name_it: str
    sipri: str
    nato: str | None  # None se non membro NATO
    eu27: bool


COUNTRIES: list[Country] = [
    Country("AT", "AUT", "Austria", "Austria", "Austria", None, True),
    Country("BE", "BEL", "Belgium", "Belgio", "Belgium", "Belgium", True),
    Country("BG", "BGR", "Bulgaria", "Bulgaria", "Bulgaria", "Bulgaria", True),
    Country("HR", "HRV", "Croatia", "Croazia", "Croatia", "Croatia", True),
    Country("CY", "CYP", "Cyprus", "Cipro", "Cyprus", None, True),
    Country("CZ", "CZE", "Czechia", "Cechia", "Czechia", "Czechia", True),
    Country("DK", "DNK", "Denmark", "Danimarca", "Denmark", "Denmark", True),
    Country("EE", "EST", "Estonia", "Estonia", "Estonia", "Estonia", True),
    Country("FI", "FIN", "Finland", "Finlandia", "Finland", "Finland", True),
    Country("FR", "FRA", "France", "Francia", "France", "France", True),
    Country("DE", "DEU", "Germany", "Germania", "Germany", "Germany", True),
    Country("EL", "GRC", "Greece", "Grecia", "Greece", "Greece", True),
    Country("HU", "HUN", "Hungary", "Ungheria", "Hungary", "Hungary", True),
    Country("IE", "IRL", "Ireland", "Irlanda", "Ireland", None, True),
    Country("IT", "ITA", "Italy", "Italia", "Italy", "Italy", True),
    Country("LV", "LVA", "Latvia", "Lettonia", "Latvia", "Latvia", True),
    Country("LT", "LTU", "Lithuania", "Lituania", "Lithuania", "Lithuania", True),
    Country("LU", "LUX", "Luxembourg", "Lussemburgo", "Luxembourg", "Luxembourg", True),
    Country("MT", "MLT", "Malta", "Malta", "Malta", None, True),
    Country("NL", "NLD", "Netherlands", "Paesi Bassi", "Netherlands", "Netherlands", True),
    Country("PL", "POL", "Poland", "Polonia", "Poland", "Poland", True),
    Country("PT", "PRT", "Portugal", "Portogallo", "Portugal", "Portugal", True),
    Country("RO", "ROU", "Romania", "Romania", "Romania", "Romania", True),
    Country("SK", "SVK", "Slovakia", "Slovacchia", "Slovakia", "Slovak Republic", True),
    Country("SI", "SVN", "Slovenia", "Slovenia", "Slovenia", "Slovenia", True),
    Country("ES", "ESP", "Spain", "Spagna", "Spain", "Spain", True),
    Country("SE", "SWE", "Sweden", "Svezia", "Sweden", "Sweden", True),
    # Europei non UE
    Country("UK", "GBR", "United Kingdom", "Regno Unito", "United Kingdom", "United Kingdom", False),
    Country("NO", "NOR", "Norway", "Norvegia", "Norway", "Norway", False),
    Country("CH", "CHE", "Switzerland", "Svizzera", "Switzerland", None, False),
    Country("IS", "ISL", "Iceland", "Islanda", "Iceland", None, False),
    Country("TR", "TUR", "Türkiye", "Turchia", "Türkiye", "Türkiye", False),
    Country("AL", "ALB", "Albania", "Albania", "Albania", "Albania", False),
    Country("ME", "MNE", "Montenegro", "Montenegro", "Montenegro", "Montenegro", False),
    Country("MK", "MKD", "North Macedonia", "Macedonia del Nord", "North Macedonia", "North Macedonia", False),
    Country("UA", "UKR", "Ukraine", "Ucraina", "Ukraine", None, False),
    Country("RU", "RUS", "Russia", "Russia", "Russia", None, False),
    # Extra-europei NATO (per i confronti con i totali)
    Country("US", "USA", "United States", "Stati Uniti", "United States of America", "United States", False),
    Country("CA", "CAN", "Canada", "Canada", "Canada", "Canada", False),
]

BY_GEO: dict[str, Country] = {c.geo: c for c in COUNTRIES}
BY_SIPRI: dict[str, Country] = {c.sipri: c for c in COUNTRIES}
BY_NATO: dict[str, Country] = {c.nato: c for c in COUNTRIES if c.nato}
EU27: list[str] = [c.geo for c in COUNTRIES if c.eu27]

# Aggregati NATO che compaiono nelle tabelle (mantenuti con un codice fittizio)
NATO_AGGREGATES: dict[str, str] = {
    "NATO Europe and Canada": "NATO_EUR_CAN",
    "NATO Total": "NATO_TOTAL",
}

# Aggregati Eurostat
EUROSTAT_AGGREGATES: dict[str, str] = {
    "EU27_2020": "UE27",
    "EA20": "Area euro",
    "NATO_EUR_CAN": "NATO Europa e Canada",
    "NATO_TOTAL": "NATO totale",
}


def name_it(geo: str) -> str:
    """Nome italiano per un codice Eurostat (o per un aggregato)."""
    if geo in BY_GEO:
        return BY_GEO[geo].name_it
    return EUROSTAT_AGGREGATES.get(geo, geo)


def clean_nato_name(raw: str) -> str:
    """Normalizza le etichette NATO: toglie "(Euros)", l'asterisco della Slovenia ecc."""
    name = raw.split(" (")[0].strip()
    return name.rstrip("*").strip()
