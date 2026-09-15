"""Test dei parser (JSON-stat e tabelle NATO) su dati sintetici."""

from cannoli.countries import BY_NATO, BY_SIPRI, EU27, clean_nato_name, name_it
from cannoli.transform import _nato_blocks, jsonstat_to_frame


def test_jsonstat_to_frame_unravels_indices():
    data = {
        "id": ["geo", "time"],
        "size": [2, 3],
        "dimension": {
            "geo": {"category": {"index": {"IT": 0, "DE": 1}}},
            "time": {"category": {"index": {"2022": 0, "2023": 1, "2024": 2}}},
        },
        # indice piatto: geo*3 + time
        "value": {"0": 1.0, "2": 3.0, "4": 5.0},
    }
    df = jsonstat_to_frame(data)
    rows = {(r.geo, r.time): r.value for r in df.itertuples()}
    assert rows == {("IT", "2022"): 1.0, ("IT", "2024"): 3.0, ("DE", "2023"): 5.0}


def test_nato_blocks_split_on_header_rows():
    rows = [
        ("Table X", None, None),
        ("Million euros", None, None),
        ("Current prices", None, None),
        (None, 2014, "2025e"),
        ("Italy (Euros)", 10, 20),
        ("NATO Total", 100, 200),
        (None, None, None),
        ("Constant 2021 prices", None, None),
        (None, 2014, "2025e"),
        ("Italy (Euros)", 11, 21),
        (None, None, None),
        ("Notes: stime", None, None),
    ]
    blocks = _nato_blocks(rows)
    assert [b[0] for b in blocks] == ["Current prices", "Constant 2021 prices"]
    assert blocks[0][2][0][0] == "Italy (Euros)"
    assert len(blocks[0][2]) == 2
    assert len(blocks[1][2]) == 1


def test_country_registry_is_consistent():
    assert len(EU27) == 27
    assert clean_nato_name("Slovenia*") == "Slovenia"
    assert clean_nato_name("Italy (Euros)") == "Italy"
    assert BY_NATO["Slovak Republic"].geo == "SK"
    assert BY_SIPRI["Czechia"].geo == "CZ"
    assert name_it("EL") == "Grecia"
    assert name_it("EU27_2020") == "UE27"
