"""Small, reviewed discovery lists; names and facts are fetched from Wikidata.

These are identity catalogs, never assertions of participation in a season.
Add a collection here after verifying its identifiers and domain classification.
"""

CONFEDERATIONS = [
    {"qid": qid, "entity_type": "confederation", "preferred_name": name}
    for qid, name in [
        ("Q35572", "UEFA"),
        ("Q58733", "CONMEBOL"),
        ("Q160549", "CONCACAF"),
        ("Q168360", "CAF"),
        ("Q83276", "AFC"),
        ("Q180344", "OFC"),
    ]
]

COLOMBIA = (
    [CONFEDERATIONS[1]]
    + [
        {
            "qid": qid,
            "entity_type": "competition",
            "tipo": kind,
            "country_qid": "Q739",
            "pais": "Colombia",
            "confederation_qid": "Q58733",
        }
        for qid, kind in [
            ("Q1033349", "liga_nacional"),
            ("Q635198", "liga_nacional"),
            ("Q1543206", "copa_nacional"),
        ]
    ]
    + [
        {
            "qid": qid,
            "entity_type": "team",
            "tipo": "club",
            "country_qid": "Q739",
            "pais": "Colombia",
            "confederation_qid": "Q58733",
        }
        for qid in [
            "Q332532",
            "Q332605",
            "Q391984",
            "Q391987",
            "Q663400",
            "Q1424072",
            "Q332527",
            "Q47533",
            "Q515178",
            "Q757418",
            "Q332858",
            "Q332668",
            "Q332636",
            "Q332863",
            "Q332833",
            "Q616380",
            "Q392284",
        ]
    ]
)

COLLECTIONS = {
    "confederaciones": {
        "name": "Las seis confederaciones",
        "description": "Identidad de las seis confederaciones continentales de fútbol.",
        "entries": CONFEDERATIONS,
    },
    "colombia": {
        "name": "Colombia · catálogo inicial",
        "description": "CONMEBOL, tres competiciones y 17 clubes. Lista inicial; no representa participantes de una temporada.",
        "entries": COLOMBIA,
    },
}
