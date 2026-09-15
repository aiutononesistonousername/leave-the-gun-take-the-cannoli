"""Leave the gun, take the cannoli.

Pipeline di analisi della spesa militare europea e italiana a confronto con
sanità e istruzione, con proiezioni al 2035 (impegno NATO del 5% del PIL).

Moduli:
- config       costanti, percorsi, parametri degli scenari
- countries    anagrafica paesi (codici Eurostat, nomi SIPRI/NATO, nomi italiani)
- sources      download e cache delle fonti (Eurostat, SIPRI, NATO, IMF)
- transform    conversione delle fonti in tabelle tidy (CSV)
- projections  proiezione del PIL e scenari di spesa 2026-2035
- charts       grafici (matplotlib)
- report       tabelle e riepilogo in Markdown
"""

__version__ = "0.1.0"
