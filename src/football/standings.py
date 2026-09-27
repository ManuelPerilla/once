"""Deterministic standings calculation; only finalized matches are supplied."""

from src.models import StandingRow


def calculate_standings(teams, matches):
    rows = {
        team.id: {
            "team": team,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
        }
        for team in teams
    }

    for match in matches:
        if match.equipo_local_id not in rows or match.equipo_visitante_id not in rows:
            continue

        home = rows[match.equipo_local_id]
        away = rows[match.equipo_visitante_id]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += match.marcador_local
        home["goals_against"] += match.marcador_visitante
        away["goals_for"] += match.marcador_visitante
        away["goals_against"] += match.marcador_local

        if match.marcador_local > match.marcador_visitante:
            home["won"] += 1
            home["points"] += 3
            away["lost"] += 1
        elif match.marcador_local < match.marcador_visitante:
            away["won"] += 1
            away["points"] += 3
            home["lost"] += 1
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += 1
            away["points"] += 1

    ordered = sorted(
        rows.values(),
        key=lambda row: (
            row["points"],
            row["goals_for"] - row["goals_against"],
            row["goals_for"],
            row["team"].nombre,
        ),
        reverse=True,
    )

    return [
        StandingRow(
            rank=index,
            goal_difference=row["goals_for"] - row["goals_against"],
            **row,
        )
        for index, row in enumerate(ordered, start=1)
    ]
