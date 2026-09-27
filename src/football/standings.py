"""Deterministic standings with explicit, versioned sporting rules."""

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models import EstadoPartido, StandingRow

CRITERIA = {
    "goal_difference",
    "goals_for",
    "wins",
    "away_goals_for",
    "away_wins",
    "head_to_head_points",
    "head_to_head_goal_difference",
    "head_to_head_goals_for",
}


class StandingsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points_win: int = Field(default=3, ge=0, le=10)
    points_draw: int = Field(default=1, ge=0, le=10)
    points_loss: int = Field(default=0, ge=0, le=10)
    tiebreakers: list[str] = Field(default_factory=lambda: ["goal_difference", "goals_for"])
    included_phase_ids: list[int] | None = None
    include_awarded: bool = False

    @model_validator(mode="after")
    def valid_criteria(self):
        if len(set(self.tiebreakers)) != len(self.tiebreakers) or set(self.tiebreakers) - CRITERIA:
            raise ValueError("Desempate desconocido o repetido; requiere una regla implementada")
        if self.included_phase_ids is not None and (
            not self.included_phase_ids or any(value <= 0 for value in self.included_phase_ids)
        ):
            raise ValueError("Una clasificación acumulada necesita fases explícitas")
        return self


def calculate_standings(teams, matches, *, rules=None, adjustments=None):
    rules = (
        rules if isinstance(rules, StandingsConfig) else StandingsConfig.model_validate(rules or {})
    )
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
            "away_goals_for": 0,
            "away_wins": 0,
        }
        for team in teams
    }
    final_states = {EstadoPartido.FINALIZADO}
    if rules.include_awarded:
        final_states.add(EstadoPartido.ADJUDICADO)
    valid = [
        match
        for match in matches
        if getattr(match, "estado", EstadoPartido.FINALIZADO) in final_states
        and match.marcador_local is not None
        and match.marcador_visitante is not None
        and match.equipo_local_id in rows
        and match.equipo_visitante_id in rows
    ]

    def add_result(target, match):
        home, away = target[match.equipo_local_id], target[match.equipo_visitante_id]
        for row, goals_for, goals_against in (
            (home, match.marcador_local, match.marcador_visitante),
            (away, match.marcador_visitante, match.marcador_local),
        ):
            row["played"] += 1
            row["goals_for"] += goals_for
            row["goals_against"] += goals_against
            result = (
                "won"
                if goals_for > goals_against
                else "lost"
                if goals_for < goals_against
                else "drawn"
            )
            row[result] += 1
            row["points"] += {
                "won": rules.points_win,
                "drawn": rules.points_draw,
                "lost": rules.points_loss,
            }[result]
        away["away_goals_for"] += match.marcador_visitante
        away["away_wins"] += int(match.marcador_visitante > match.marcador_local)

    for match in valid:
        add_result(rows, match)
    for team_id, points in (adjustments or {}).items():
        if team_id in rows:
            rows[team_id]["points"] += points

    def metric(row, criterion):
        if criterion == "goal_difference":
            return row["goals_for"] - row["goals_against"]
        return row["won" if criterion == "wins" else criterion]

    def ordered_groups(group, criteria):
        if len(group) <= 1 or not criteria:
            return [
                sorted(group, key=lambda item: (item["team"].nombre.casefold(), item["team"].id))
            ]
        criterion, *remaining = criteria
        values = group
        if criterion.startswith("head_to_head_"):
            ids = {row["team"].id for row in group}
            mini = {
                key: {name: value if name == "team" else 0 for name, value in rows[key].items()}
                for key in ids
            }
            for match in valid:
                if match.equipo_local_id in ids and match.equipo_visitante_id in ids:
                    add_result(mini, match)
            values = [mini[row["team"].id] for row in group]
            criterion = criterion.removeprefix("head_to_head_")
        buckets = defaultdict(list)
        for original, value in zip(group, values, strict=True):
            buckets[metric(value, criterion)].append(original)
        return [
            subgroup
            for key in sorted(buckets, reverse=True)
            for subgroup in ordered_groups(buckets[key], remaining)
        ]

    result, rank = [], 1
    for tied in ordered_groups(list(rows.values()), ["points", *rules.tiebreakers]):
        for row in tied:
            public = {
                key: value
                for key, value in row.items()
                if key not in {"away_goals_for", "away_wins"}
            }
            result.append(
                StandingRow(rank=rank, goal_difference=metric(row, "goal_difference"), **public)
            )
        rank += len(tied)
    return result
