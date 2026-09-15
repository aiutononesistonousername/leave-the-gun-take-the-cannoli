"""Leave the gun, take the cannoli - entrypoint della pipeline.

Uso:
    python main.py                   scarica (se serve), trasforma, proietta, disegna
    python main.py --refresh         forza il nuovo download delle fonti
    python main.py --from-processed  salta download e trasformazione, usa i CSV in data/processed
    python main.py --no-charts       calcola solo tabelle e riepilogo
"""

from __future__ import annotations

import argparse
import logging
import sys

from cannoli import charts, config, projections, report, sources, transform


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spesa militare vs sanità e istruzione: pipeline di analisi.")
    parser.add_argument("--refresh", action="store_true", help="riscarica le fonti anche se presenti in data/raw")
    parser.add_argument("--from-processed", action="store_true", help="usa i CSV in data/processed senza scaricare")
    parser.add_argument("--no-charts", action="store_true", help="non generare i grafici")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("main")

    if args.from_processed:
        log.info("lettura dei CSV in %s", config.DATA_PROCESSED)
        data = transform.read_processed()
    else:
        paths = sources.fetch_all(refresh=args.refresh)
        data = transform.load_all(paths)

    gdp, scen, summary = projections.run(data)
    if not args.no_charts:
        charts.render_all(data, scen, summary)
    tables = report.write_tables(data, scen)
    text = report.write_summary(summary, scen, tables)

    print()
    print(text)
    log.info("fatto: grafici in %s, tabelle in %s", config.CHARTS, config.TABLES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
