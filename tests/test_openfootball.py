"""CC0 archive parsing and publication: no penalties as goals, no fuzzy merges."""

from types import SimpleNamespace

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.audit.service import apply_source_changes
from src.models import (
    AuditChange,
    DataIssue,
    Equipo,
    EstadoPartido,
    ParticipacionFase,
    ParticipacionGrupo,
    Partido,
    ProviderMapping,
    ProviderSnapshot,
    Temporada,
)
from src.providers.openfootball import (
    OpenFootballHandler,
    parse_archive,
    parse_score,
    source_id,
    validate_selector,
)
from src.sync.handlers import JobContext
from src.sync.models import SyncIssue, SyncScope
from src.sync.service import PermanentError

# Short CC0 examples from openfootball/south-america/colombia/2025_co1.txt.
ARCHIVE = """= Colombia Primera A 2025
# Teams      4
# Matches    3
▪ Apertura, Matchday 1
  Fri Jan 24 2025
    18:00  Boyacá Chicó            v Atlético Bucaramanga     1-0 (1-0)
▪ Apertura, Matchday 17
  Sun May 4
    18:20  Unión Magdalena         v Once Caldas              [abandoned]
▪ Apertura, Matchday 20
  Sun May 25
           Boyacá Chicó            v Atlético Bucaramanga
"""


def context():
    return JobContext("archive-test", "archive-scope", 1, "test", lambda *_: None, lambda **_: None)


def test_archive_preserves_absent_scores_and_source_times():
    result = parse_archive(ARCHIVE, 2025)
    assert result["coverage"]["missing_results"] == 2
    assert result["coverage"]["live"] is False
    first, abandoned, unknown = result["fixtures"]
    assert (first["home"], first["score_home"], first["date"]) == ("Boyacá Chicó", 1, "2025-01-24")
    assert abandoned["status"] == "abandoned" and abandoned["score_home"] is None
    assert unknown["status"] == "unknown" and unknown["time"] is None


@pytest.mark.parametrize(
    "score,expected",
    [
        ("5-6 pen. (3-2, 1-1)", (3, 2, "penalties", [5, 6])),
        ("3-2 pen. 1-1 a.e.t. (1-1, 0-1)", (1, 1, "penalties", [3, 2])),
        ("3-0    [awarded]", (3, 0, "awarded", None)),
        ("0-0", (0, 0, "finished", None)),
    ],
)
def test_penalty_shootout_is_separate_from_match_score(score, expected):
    assert parse_score(score) == expected


@pytest.mark.parametrize(
    "text,year",
    [
        (ARCHIVE.replace("# Matches    3", "# Matches    4"), 2025),
        (ARCHIVE.replace("1-0 (1-0)", "?unknown score?"), 2025),
        (ARCHIVE.replace("Fri Jan 24", "Fri Jan 99"), 2025),
        (ARCHIVE, 2026),
        (ARCHIVE + "unexpected format change\n", 2025),
    ],
)
def test_archive_rejects_truncation_unknown_format_and_wrong_year(text, year):
    with pytest.raises(ValueError):
        parse_archive(text, year)


def test_scope_cannot_select_arbitrary_urls_or_current_live_year():
    with pytest.raises(ValueError):
        validate_selector({"season": "../2026"})
    with pytest.raises(ValueError):
        validate_selector({"season": 2026})
    with pytest.raises(ValueError):
        validate_selector({"timezone": "UTC"})


def test_fetch_reserves_quota_once_and_downloads_only_allowlisted_path(monkeypatch):
    calls, reservations = [], []

    def transport(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=ARCHIVE)

    original = httpx.Client
    monkeypatch.setattr(
        "src.providers.openfootball.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(transport), **kw),
    )
    task = context()
    task.reserve_request = reservations.append
    observed = OpenFootballHandler().fetch(
        SimpleNamespace(selector={"season": 2025, "url": "https://attacker.invalid"}), task
    )
    assert observed.complete
    assert reservations == ["openfootball"]
    assert calls == [
        "https://raw.githubusercontent.com/openfootball/south-america/master/colombia/2025_co1.txt"
    ]


def test_oversized_response_rejected_before_publication(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(
        "src.providers.openfootball.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 1048577)),
            **kw,
        ),
    )
    with pytest.raises(PermanentError):
        OpenFootballHandler().fetch(SimpleNamespace(selector={"season": 2025}), context())


def prepared(session, competition_id, **selector):
    scope = SyncScope(
        name="Archivo 2025",
        provider="openfootball",
        kind="archive",
        selector={"season": 2025, "competition_id": competition_id, **selector},
    )
    session.add(scope)
    session.flush()
    return scope


def test_archival_publication_is_repeatable_and_never_assumes_missing_timezone(catalog):
    with Session(database.engine) as session:
        scope = prepared(session, catalog["comp"]["id"])
        handler, payload = OpenFootballHandler(), parse_archive(ARCHIVE, 2025)
        first = handler.apply(session, scope, payload, context())
        session.commit()
        second = handler.apply(session, scope, payload, context())
        session.commit()
        assert first["imported"] == 3 and second["changed"] == 0
        matches = session.exec(select(Partido)).all()
        assert len(matches) == 3 and all(match.fecha is None for match in matches)
        assert {match.estado for match in matches} == {
            EstadoPartido.FINALIZADO,
            EstadoPartido.ABANDONADO,
            EstadoPartido.DESCONOCIDO,
        }
        assert len(session.exec(select(Temporada)).all()) == 1
        assert session.exec(
            select(SyncIssue).where(SyncIssue.code == "archive_incomplete_results")
        ).first()


def test_explicit_timezone_converts_times_and_keeps_unspecified_time_unknown(catalog):
    with Session(database.engine) as session:
        scope = prepared(session, catalog["comp"]["id"], timezone="America/Bogota")
        OpenFootballHandler().apply(session, scope, parse_archive(ARCHIVE, 2025), context())
        session.commit()
        match = session.exec(
            select(Partido).where(Partido.estado == EstadoPartido.FINALIZADO)
        ).one()
        assert match.fecha.isoformat() == "2025-01-24T23:00:00+00:00"
        missing = session.exec(
            select(Partido).where(Partido.estado == EstadoPartido.DESCONOCIDO)
        ).one()
        assert missing.fecha is None


def test_existing_team_name_is_reviewed_never_automatically_merged(catalog):
    with Session(database.engine) as session:
        existing = Equipo(nombre="Boyacá Chicó", logo="", tipo="club", pais="Colombia")
        session.add(existing)
        session.commit()
        scope = prepared(session, catalog["comp"]["id"])
        result = OpenFootballHandler().apply(
            session, scope, parse_archive(ARCHIVE, 2025), context()
        )
        session.commit()
        assert result["imported"] == 1 and result["skipped"] == 2
        assert session.exec(select(SyncIssue).where(SyncIssue.code.like("identity:team:%"))).first()
        assert not session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "openfootball",
                ProviderMapping.entity_type == "team",
                ProviderMapping.local_id == existing.id,
            )
        ).first()


def test_unknown_archive_results_do_not_erase_later_verified_scores(catalog):
    with Session(database.engine) as session:
        scope = prepared(session, catalog["comp"]["id"])
        handler = OpenFootballHandler()
        handler.apply(session, scope, parse_archive(ARCHIVE, 2025), context())
        session.commit()
        known = session.exec(
            select(Partido).where(Partido.estado == EstadoPartido.FINALIZADO)
        ).one()
        changed_archive = ARCHIVE.replace("1-0 (1-0)", "")
        handler.apply(session, scope, parse_archive(changed_archive, 2025), context())
        session.commit()
        session.refresh(known)
        assert known.marcador_local == 1 and known.estado == EstadoPartido.FINALIZADO
        snapshot = session.exec(
            select(ProviderSnapshot).where(
                ProviderSnapshot.entity_type == "match", ProviderSnapshot.local_id == known.id
            )
        ).first()
        assert snapshot.payload["status"] == "unknown"


def test_created_matches_phases_groups_and_enrollments_are_audited_once(catalog):
    text = (
        ARCHIVE.replace("# Matches    3", "# Matches    4")
        + """
▪ Apertura Playoffs, Group A
  Sun May 25
    18:00  Unión Magdalena         v Once Caldas              1-0 (0-0)
"""
    )
    with Session(database.engine) as session:
        scope = prepared(session, catalog["comp"]["id"])
        handler, payload = OpenFootballHandler(), parse_archive(text, 2025)
        handler.apply(session, scope, payload, context())
        session.commit()
        rows = session.exec(select(AuditChange).where(AuditChange.source == "openfootball")).all()
        created = [row for row in rows if row.action == "source_create"]
        assert len([row for row in created if row.entity_type == "match"]) == 4
        assert len([row for row in created if row.entity_type == "stage"]) == 2
        assert len([row for row in created if row.entity_type == "group"]) == 1
        assert all(row.actor == "service:sync" and row.run_id == "archive-test" for row in created)
        assert any(row.action == "source_enrollment" for row in rows)
        assert all(row.source == "openfootball" for row in session.exec(select(ParticipacionFase)))
        assert all(row.source == "openfootball" for row in session.exec(select(ParticipacionGrupo)))
        first_count = len(rows)
        handler.apply(session, scope, payload, context())
        session.commit()
        repeated = session.exec(
            select(AuditChange).where(AuditChange.source == "openfootball")
        ).all()
        assert len(repeated) == first_count


def linked_club(session, name, qid):
    team = Equipo(nombre=name, logo="", tipo="club", pais="Colombia")
    session.add(team)
    session.flush()
    session.add(
        ProviderMapping(provider="wikidata", entity_type="team", local_id=team.id, external_id=qid)
    )
    session.flush()
    return team


def test_verified_archive_labels_reuse_existing_wikidata_clubs(catalog):
    with Session(database.engine) as session:
        expected = {
            label: linked_club(session, label, qid).id
            for label, qid in (
                ("Boyacá Chicó", "Q332863"),
                ("Atlético Bucaramanga", "Q757418"),
                ("Once Caldas", "Q47533"),
            )
        }
        count_before = len(session.exec(select(Equipo)).all())
        scope = prepared(session, catalog["comp"]["id"])
        handler, payload = OpenFootballHandler(), parse_archive(ARCHIVE, 2025)
        result = handler.apply(session, scope, payload, context())
        session.commit()
        assert result["imported"] == 3 and result["skipped"] == 0
        # Only Unión Magdalena lacks an existing canonical link in this fixture.
        assert len(session.exec(select(Equipo)).all()) == count_before + 1
        assert (
            len(
                session.exec(
                    select(ProviderMapping).where(ProviderMapping.provider == "wikidata")
                ).all()
            )
            == 3
        )
        for label, team_id in expected.items():
            mapping = session.exec(
                select(ProviderMapping).where(
                    ProviderMapping.provider == "openfootball",
                    ProviderMapping.entity_type == "team",
                    ProviderMapping.external_id == f"colombia/{source_id(label)}",
                )
            ).one()
            assert mapping.local_id == team_id
        assert not session.exec(
            select(SyncIssue).where(SyncIssue.code.like("identity:team:%"))
        ).first()
        assert handler.apply(session, scope, payload, context())["changed"] == 0


@pytest.mark.parametrize("reviewed_selection", [False, True])
def test_historical_alias_preserves_canonical_name_without_false_issue(catalog, reviewed_selection):
    with Session(database.engine) as session:
        team = linked_club(session, "Internacional Bogotá", "Q332668")
        apply_source_changes(session, "team", team, {"nombre": team.nombre}, source="wikidata")
        scope = prepared(
            session,
            catalog["comp"]["id"],
            **({"team_ids": {"La Equidad": team.id}} if reviewed_selection else {}),
        )
        handler = OpenFootballHandler()
        payload = parse_archive(ARCHIVE.replace("Boyacá Chicó", "La Equidad"), 2025)
        assert handler.apply(session, scope, payload, context())["imported"] == 3
        session.commit()
        session.refresh(team)
        assert team.nombre == "Internacional Bogotá"
        assert not session.exec(
            select(DataIssue).where(DataIssue.entity_type == "team", DataIssue.entity_id == team.id)
        ).first()
        assert not session.exec(
            select(SyncIssue).where(SyncIssue.code.like("identity:team:%"))
        ).first()
        snapshot = session.exec(
            select(ProviderSnapshot).where(
                ProviderSnapshot.provider == "openfootball",
                ProviderSnapshot.entity_type == "team",
                ProviderSnapshot.local_id == team.id,
            )
        ).one()
        assert snapshot.payload["source_label"] == "La Equidad"
        assert snapshot.payload["wikidata_qid"] == "Q332668"
        assert snapshot.payload["historical"] is True
        assert snapshot.payload["year"] == 2025
        assert snapshot.payload["source_url"] == payload["source_url"]
        assert handler.apply(session, scope, payload, context())["changed"] == 0


@pytest.mark.parametrize("conflict", ["reviewed", "provider_mapping"])
def test_conflicting_club_links_stop_publication(catalog, conflict):
    with Session(database.engine) as session:
        canonical = linked_club(session, "Internacional Bogotá", "Q332668")
        other_id = catalog["teams"][0]["id"]
        scope = prepared(
            session,
            catalog["comp"]["id"],
            **({"team_ids": {"La Equidad": other_id}} if conflict == "reviewed" else {}),
        )
        if conflict == "provider_mapping":
            session.add(
                ProviderMapping(
                    provider="openfootball",
                    entity_type="team",
                    local_id=other_id,
                    external_id=f"colombia/{source_id('La Equidad')}",
                )
            )
        session.commit()
        with pytest.raises(PermanentError, match="La Equidad.*clubes diferentes"):
            OpenFootballHandler().apply(
                session,
                scope,
                parse_archive(ARCHIVE.replace("Boyacá Chicó", "La Equidad"), 2025),
                context(),
            )
        session.rollback()
        assert not session.exec(select(Partido)).first()
        assert session.get(Equipo, canonical.id).nombre == "Internacional Bogotá"


def test_crosswalk_does_not_match_unreviewed_spelling(catalog):
    with Session(database.engine) as session:
        canonical = linked_club(session, "Internacional Bogotá", "Q332668")
        scope = prepared(session, catalog["comp"]["id"])
        label = "Equidad"
        OpenFootballHandler().apply(
            session,
            scope,
            parse_archive(ARCHIVE.replace("Boyacá Chicó", label), 2025),
            context(),
        )
        session.commit()
        source = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "openfootball",
                ProviderMapping.entity_type == "team",
                ProviderMapping.external_id == f"colombia/{source_id(label)}",
            )
        ).one()
        assert source.local_id != canonical.id


def test_crosswalk_is_limited_to_verified_archive_year(catalog):
    text = (
        ARCHIVE.replace("2025", "2024")
        .replace("Fri Jan 24", "Wed Jan 24")
        .replace("Sun May 4", "Sat May 4")
        .replace("Sun May 25", "Sat May 25")
    )
    with Session(database.engine) as session:
        canonical = linked_club(session, "Boyacá Chicó", "Q332863")
        scope = prepared(session, catalog["comp"]["id"], season=2024)
        result = OpenFootballHandler().apply(session, scope, parse_archive(text, 2024), context())
        session.commit()
        assert result["imported"] == 1 and result["skipped"] == 2
        assert not session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "openfootball",
                ProviderMapping.entity_type == "team",
                ProviderMapping.local_id == canonical.id,
            )
        ).first()
