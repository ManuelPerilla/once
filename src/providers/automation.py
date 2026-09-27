"""Verified observations become canonical data only inside the worker's fence."""

import datetime as dt
import re
import time
from difflib import SequenceMatcher
from types import SimpleNamespace

import httpx
from sqlmodel import select

from src.audit.service import apply_source_changes, record_change
from src.catalog.collections import COLLECTIONS
from src.catalog.service import _key, normalize
from src.football.entities import ENTITY_MODELS
from src.models import (
    MediaAsset,
    OfficialStandingSnapshot,
    Participacion,
    ProviderMapping,
    ProviderSnapshot,
    TipoCompeticion,
    TipoEquipo,
)
from src.providers import APIFootballClient, ProviderError, ProviderNotConfigured, WikidataClient
from src.providers.media_cache import batch_crests, cache_asset
from src.providers.sync import sync_competition_fixtures, sync_match_detail
from src.sync.handlers import FetchResult
from src.sync.service import PermanentError, RetryableError, issue


def _integer(selector, key):
    try:
        value = int(selector[key])
        if value <= 0:
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError) as exc:
        raise PermanentError(f"Configura {key} con un identificador válido.") from exc


def _mapped(session, provider, kind, external_id, scope=""):
    return session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == provider,
            ProviderMapping.entity_type == kind,
            ProviderMapping.external_id == str(external_id),
            ProviderMapping.external_scope == scope,
        )
    ).first()


def _snapshot(session, provider, kind, entity_id, category, payload):
    item = session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == provider,
            ProviderSnapshot.entity_type == kind,
            ProviderSnapshot.local_id == entity_id,
            ProviderSnapshot.kind == category,
        )
    ).first()
    changed = item is None or item.payload != payload
    if item is None:
        item = ProviderSnapshot(
            provider=provider, entity_type=kind, local_id=entity_id, kind=category, payload=payload
        )
    else:
        item.payload, item.fetched_at = payload, dt.datetime.now(dt.UTC)
    session.add(item)
    return int(changed)


class Transport:
    def __init__(self, context, client):
        self.context, self.client = context, client

    def __call__(self, url, **kwargs):
        provider = (
            "api-football"
            if url.startswith(APIFootballClient.base_url)
            else "commons"
            if ".wikimedia.org/" in url
            else "wikidata"
        )
        from src.sync.service import PacingWait

        for attempt in range(3):
            try:
                self.context.reserve_request(provider)
                break
            except PacingWait as exc:
                delay = max(0.01, float(exc.retry_after or 0))
                if delay > 10 or attempt == 2:
                    raise
                # Reservations and HTTP both happen outside the canonical transaction.
                # The next reservation rechecks pause epochs and the job lease.
                time.sleep(delay)
        limit = kwargs.pop("max_bytes", 8 * 1024 * 1024)
        with self.client.stream("GET", url, **kwargs) as remote:
            body = bytearray()
            for chunk in remote.iter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise PermanentError(
                        "La respuesta supera el tamaño permitido para una actualización."
                    )
            headers = remote.headers.copy()
            # iter_bytes already decompresses the wire body. Reusing its encoding
            # header would make httpx decompress JSON/images a second time.
            headers.pop("content-encoding", None)
            headers.pop("content-length", None)
            response = httpx.Response(
                remote.status_code,
                headers=headers,
                content=bytes(body),
                request=remote.request,
            )

        def integer(name):
            value = response.headers.get(name)
            return int(value) if value and value.isdigit() else None

        retry_after = integer("Retry-After")
        self.context.report_quota(
            provider=provider,
            limit_day=integer("x-ratelimit-requests-limit"),
            limit_minute=integer("x-ratelimit-limit"),
            remaining_day=integer("x-ratelimit-requests-remaining"),
            remaining_minute=integer("x-ratelimit-remaining"),
            retry_after=retry_after,
        )
        return response


def _fetch(call, context):
    try:
        with httpx.Client(
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            follow_redirects=False,
        ) as client:
            return call(Transport(context, client))
    except ProviderNotConfigured as exc:
        raise PermanentError(str(exc)) from exc
    except ProviderError as exc:
        if not exc.retryable:
            raise PermanentError(str(exc)) from exc
        retry = float(exc.retry_after) if str(exc.retry_after).isdigit() else None
        raise RetryableError(str(exc), retry_after=retry) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise PermanentError("La fuente o la selección no tienen el formato esperado.") from exc


def _identity(
    session, scope, kind, external_id, values, *, external_scope="", context=None, target_id=None
):
    model = ENTITY_MODELS[kind]
    mapping = _mapped(session, scope.provider, kind, external_id, external_scope)
    item = session.get(model, mapping.local_id) if mapping else None
    if mapping and target_id and mapping.local_id != int(target_id):
        raise PermanentError("La identidad externa ya está vinculada a otra ficha local.")
    if mapping and item is None:
        issue(
            session,
            scope.id,
            f"missing:{kind}:{external_id}",
            "Un vínculo apunta a una ficha eliminada.",
        )
        return None, 0
    if item is None and target_id:
        # An explicit administrator choice is a reviewed identity, not fuzzy matching.
        item = session.get(model, int(target_id))
        if not item:
            raise PermanentError("La ficha local seleccionada ya no existe.")
        if kind == "season" and item.competicion_id != values["competicion_id"]:
            raise PermanentError("La edición seleccionada pertenece a otra competición.")
        if kind in {"team", "competition"} and item.tipo != values.get("tipo"):
            raise PermanentError("La ficha seleccionada pertenece a otra categoría.")
        if hasattr(item, "pais") and values.get("pais") and _key(item.pais) != _key(values["pais"]):
            raise PermanentError("La ficha seleccionada pertenece a otro país.")
    created = item is None
    if created:
        candidates = select(model)
        if hasattr(model, "pais") and values.get("pais"):
            candidates = candidates.where(model.pais == values["pais"])
        if kind == "season":
            candidates = candidates.where(model.competicion_id == values["competicion_id"])
        if scope.provider == "api-football" and kind in {"team", "competition"}:
            # Distinct stable IDs from the same provider are distinct identities.
            # Deportivo Cali and Deportivo Pasto are not a fuzzy collision.
            identified = select(ProviderMapping.local_id).where(
                ProviderMapping.provider == scope.provider,
                ProviderMapping.entity_type == kind,
                ProviderMapping.external_id != str(external_id),
            )
            candidates = candidates.where(model.id.not_in(identified))
        # Discovery batches are small; candidate matching only proposes review.
        expected_years = set(re.findall(r"\b(?:19|20)\d{2}\b", values["nombre"]))
        ambiguous = next(
            (
                row
                for row in session.exec(candidates).all()
                if not (
                    kind == "season"
                    and expected_years
                    and (known_years := set(re.findall(r"\b(?:19|20)\d{2}\b", row.nombre)))
                    and not expected_years & known_years
                )
                and SequenceMatcher(None, _key(row.nombre), _key(values["nombre"])).ratio() >= 0.78
            ),
            None,
        )
        if ambiguous:
            issue(
                session,
                scope.id,
                f"identity:{kind}:{external_id}:{external_scope}",
                f"{values['nombre']} puede corresponder a {ambiguous.nombre}. Conecta sus identificadores en Traer información.",
            )
            return None, 0
        item = model(**values)
        session.add(item)
        session.flush()
    if mapping is None:
        session.add(
            ProviderMapping(
                provider=scope.provider,
                entity_type=kind,
                local_id=item.id,
                external_id=str(external_id),
                external_scope=external_scope,
                verified_at=dt.datetime.now(dt.UTC),
            )
        )
        session.flush()
    values = {
        key: value
        for key, value in values.items()
        if not (key == "logo" and not value and item.logo)
    }
    fields = apply_source_changes(
        session,
        kind,
        item,
        values,
        source=scope.provider,
        run_id=context.job_id if context else None,
        observed_at=getattr(context, "observed_at", None),
    )
    if created:
        record_change(
            session,
            entity_type=kind,
            entity_id=item.id,
            field="*",
            before=None,
            after=item.model_dump(mode="json"),
            action="source_create",
            actor="service:sync",
            reason="Identidad externa nueva validada",
            version=0,
            source=scope.provider,
            run_id=context.job_id if context else None,
        )
    return item, len(fields) + int(created)


class CatalogHandler:
    def fetch(self, scope, context):
        name = scope.selector.get("collection", "colombia")
        if name not in COLLECTIONS:
            raise PermanentError("Elige una colección disponible.")
        entries = COLLECTIONS[name]["entries"]

        def call(transport):
            client = WikidataClient(transport=transport)
            entities = client.entities([entry["qid"] for entry in entries])
            payload = {"collection": name, "entities": entities, "media": {}, "media_errors": []}
            if scope.selector.get("include_media", True):
                try:
                    media = batch_crests(entities, transport, client.headers)
                    for qid, asset in media.items():
                        try:
                            payload["media"][qid] = cache_asset(asset, transport)
                        except (ProviderError, httpx.HTTPError) as exc:
                            payload["media_errors"].append(
                                {"qid": qid, "reason": type(exc).__name__}
                            )
                except (ProviderError, httpx.HTTPError):
                    payload["media_errors"].append(
                        {"qid": "commons", "reason": "temporarily_unavailable"}
                    )
            return FetchResult(payload)

        return _fetch(call, context)

    def apply(self, session, scope, payload, context):
        definition = COLLECTIONS[payload["collection"]]
        changed = 0
        for spec in definition["entries"]:
            raw = payload["entities"].get(spec["qid"], {})
            row = normalize(spec, raw)
            if row["errors"]:
                issue(session, scope.id, f"wikidata:{row['qid']}", " ".join(row["errors"]))
                continue
            kind = row["entity_type"]
            values = {"nombre": row["nombre"]}
            mapping = _mapped(session, "wikidata", kind, row["qid"])
            if not mapping:
                values["logo"] = ""
            if kind != "confederation":
                conf = _mapped(session, "wikidata", "confederation", row.get("confederation_qid"))
                if row.get("confederation_qid") and not conf:
                    issue(
                        session,
                        scope.id,
                        f"parent:{row['qid']}",
                        "Conecta primero la confederación de esta ficha.",
                    )
                    continue
                values.update(
                    tipo=row["tipo"],
                    pais=row["pais"],
                    confederacion_id=conf.local_id if conf else None,
                )
            item, count = _identity(session, scope, kind, row["qid"], values, context=context)
            changed += count
            if item:
                _snapshot(
                    session,
                    "wikidata",
                    kind,
                    item.id,
                    "catalog_identity",
                    {"classification": row, "entity": raw},
                )
                changed += _save_history(session, kind, item.id, raw, row["qid"])
                if row["qid"] in payload.get("media", {}):
                    changed += _save_media(
                        session, kind, item, payload["media"][row["qid"]], context
                    )
        for error in payload.get("media_errors", []):
            issue(
                session,
                scope.id,
                f"media:{error['qid']}",
                "El catálogo se conservó; un recurso visual sigue pendiente de una descarga válida.",
            )
        return {"changed": changed, "topics": ["catalog"], "collection": payload["collection"]}


def _save_history(session, kind, entity_id, entity, qid):
    facts = []
    properties = {
        "P571": "Fundación",
        "P1448": "Nombre oficial",
        "P1813": "Nombre abreviado",
        "P856": "Sitio oficial",
        "P159": "Sede",
        "P31": "Tipo de entidad",
    }
    for prop, label in properties.items():
        for statement in (entity.get("claims") or {}).get(prop, []):
            if statement.get("rank") == "deprecated":
                continue
            value = (statement.get("mainsnak", {}).get("datavalue") or {}).get("value")
            if value is not None:
                facts.append(
                    {
                        "property": prop,
                        "label": label,
                        "value": value,
                        "references": statement.get("references", []),
                        "qualifiers": statement.get("qualifiers", {}),
                    }
                )
    return _snapshot(
        session,
        "wikidata",
        kind,
        entity_id,
        "history",
        {
            "facts": facts,
            "revision": entity.get("lastrevid"),
            "source_url": f"https://www.wikidata.org/wiki/{qid}",
            "license": "CC0-1.0",
        },
    )


class EnrichmentHandler:
    def __init__(self, media=False):
        self.media = media

    def fetch(self, scope, context):
        qid = scope.selector.get("qid", "")

        def call(transport):
            client = WikidataClient(transport=transport)
            return FetchResult(
                cache_asset(client.commons_media(qid, purpose="crest"), transport)
                if self.media
                else client.entity(qid)
            )

        return _fetch(call, context)

    def apply(self, session, scope, payload, context):
        kind, local_id = scope.selector.get("entity_type"), _integer(scope.selector, "local_id")
        qid = str(scope.selector.get("qid", "")).upper()
        model = ENTITY_MODELS.get(kind)
        item = session.get(model, local_id) if model else None
        mapping = _mapped(session, "wikidata", kind, qid)
        if item is None or mapping is None or mapping.local_id != local_id:
            raise PermanentError(
                "Conecta la ficha y su identidad de Wikidata antes de enriquecerla."
            )
        if not self.media:
            return {
                "changed": _save_history(session, kind, local_id, payload, qid),
                "topics": ["history"],
            }
        if (
            kind not in {"team", "competition", "confederation"}
            or payload.get("property") != "P154"
            or not payload.get("license")
        ):
            raise PermanentError(
                "La fuente no ofrece un escudo con licencia identificada para esta ficha."
            )
        return {
            "changed": _save_media(session, kind, item, payload, context),
            "topics": ["catalog"],
        }


def _save_media(session, kind, item, payload, context):
    existing = session.exec(
        select(MediaAsset).where(
            MediaAsset.entity_type == kind,
            MediaAsset.entity_id == item.id,
            MediaAsset.source == "wikimedia-commons",
            MediaAsset.remote_id == payload["filename"],
        )
    ).first()
    values = {
        key: payload.get(key)
        for key in (
            "source_url",
            "author",
            "license",
            "license_url",
            "credit",
            "original_url",
            "local_url",
            "width",
            "height",
            "mime_type",
        )
    }
    changed = existing is None or any(
        getattr(existing, key) != value for key, value in values.items()
    )
    if existing is None:
        existing = MediaAsset(
            entity_type=kind,
            entity_id=item.id,
            tipo="escudo",
            source="wikimedia-commons",
            remote_id=payload["filename"],
            **values,
        )
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    existing.verified_at = dt.datetime.now(dt.UTC)
    session.add(existing)
    applied = apply_source_changes(
        session,
        kind,
        item,
        {"logo": payload.get("local_url") or payload["original_url"]},
        source="wikidata",
        observed_at=getattr(context, "observed_at", None),
        run_id=context.job_id,
    )
    return len(applied) + int(changed)


def _api_logo(value):
    """Only the provider's published image paths may become browser resources."""
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"https://media\.api-sports\.io/football/(teams|leagues)/\d+\.png", value)
        else ""
    )


def _api_metadata(session, kind, item, raw, context):
    changed = _snapshot(session, "api-football", kind, item.id, "catalog_identity", raw)
    source = raw.get("team") or raw.get("league") or {}
    logo = _api_logo(source.get("logo"))
    if logo:
        asset = session.exec(
            select(MediaAsset).where(
                MediaAsset.entity_type == kind,
                MediaAsset.entity_id == item.id,
                MediaAsset.source == "api-football",
                MediaAsset.remote_id == str(source["id"]),
            )
        ).first()
        if asset is None:
            session.add(
                MediaAsset(
                    entity_type=kind,
                    entity_id=item.id,
                    tipo="escudo",
                    source="api-football",
                    remote_id=str(source["id"]),
                    original_url=logo,
                    source_url="https://www.api-football.com/",
                    credit="API-Football / API-Sports; derechos de sus titulares",
                    verified_at=dt.datetime.now(dt.UTC),
                )
            )
            changed += 1
        if not item.logo:
            changed += len(
                apply_source_changes(
                    session,
                    kind,
                    item,
                    {"logo": logo},
                    source="api-football",
                    observed_at=getattr(context, "observed_at", None),
                    run_id=context.job_id,
                )
            )
    return changed


def _annual_women_layout(league_id, year, fixtures):
    """Verified source policy for Colombia's 712 historical women's league.

    In the 2022–2024 source format, Apertura labels the regular phase of one
    annual tournament, followed by unprefixed knockout rounds. The observed
    2024 variant includes Quadrangular Semi-finals and Championship - Final.
    Restrict the exception to this provider ID, these historical years and the
    complete known round vocabulary; unknown formats or any Clausura require
    normal edition handling/review, never an inferred annual merge.
    """
    if league_id != 712 or year not in {2022, 2023, 2024} or not fixtures:
        return False
    rounds = [str((row.get("league") or {}).get("round", "")) for row in fixtures]
    return any(re.fullmatch(r"Apertura - \d+", label) for label in rounds) and all(
        re.fullmatch(
            r"(?:Apertura - \d+|Quadrangular Semi-finals - \d+|Championship - Final|Quarter-finals|Semi-finals|Final)",
            label,
        )
        for label in rounds
    )


class DiscoveryHandler:
    def fetch(self, scope, context):
        return _fetch(
            lambda transport: FetchResult(
                APIFootballClient(transport=transport).leagues(
                    scope.selector.get("country", "Colombia")
                )
            ),
            context,
        )

    def apply(self, session, scope, payload, context):
        from src.models import Fase, Temporada
        from src.sync.models import SyncScope
        from src.sync.service import history

        coverage, prepared = [], []
        plans = session.exec(select(SyncScope)).all()
        current_year = dt.datetime.now(dt.UTC).year

        def prepare(kind, league, year, selector):
            if any(
                plan.provider == "api-football"
                and plan.kind == kind
                and plan.selector.get("league_id") == league["id"]
                and plan.selector.get("season") == year
                for plan in plans
            ):
                return
            if len(plans) >= 50:
                issue(
                    session,
                    scope.id,
                    "discovery_limit",
                    "Hay 50 ámbitos configurados. Revisa los existentes antes de añadir cobertura.",
                )
                return
            name = f"{league.get('name') or league['id']} · {year} · {'Calendario' if kind == 'fixtures' else 'Clasificación'}"
            plan = SyncScope(
                name=name[:120],
                provider="api-football",
                kind=kind,
                mode="paused",
                selector={
                    "league_id": league["id"],
                    "season": year,
                    "discovered_by": scope.id,
                    "coverage_status": "access_unverified",
                    **selector,
                },
                interval_seconds=300 if kind == "fixtures" else 3600,
                daily_limit=scope.daily_limit,
                minute_limit=scope.minute_limit,
            )
            session.add(plan)
            session.flush()
            plans.append(plan)
            prepared.append(plan.id)
            issue(
                session,
                plan.id,
                "coverage_verification",
                "Perfil preparado con la temporada publicada. Confirma el acceso de la cuenta y la edición antes de activar sus actualizaciones.",
            )
            history(
                session,
                context.actor,
                "scope_prepared",
                plan.id,
                context.job_id,
                parent_scope=scope.id,
                reason="Cobertura publicada; acceso de la cuenta pendiente de comprobar.",
            )

        for raw in payload.get("response", []):
            league, country = raw.get("league") or {}, raw.get("country") or {}
            if country.get("name") != scope.selector.get("country", "Colombia") or not league.get(
                "id"
            ):
                continue
            # A country-level discovery never assigns a generic competition type to women/youth.
            coverage.append(
                {
                    "league_id": league["id"],
                    "name": league.get("name"),
                    "seasons": raw.get("seasons", []),
                }
            )
            seasons = [
                season
                for season in raw.get("seasons", [])
                if isinstance(season, dict)
                and type(season.get("year")) is int
                and 1900 <= season["year"] <= current_year + 1
            ]
            candidates = [
                season
                for season in seasons
                if season.get("current") or season["year"] >= current_year
            ]
            if not candidates and seasons:
                candidates = [max(seasons, key=lambda season: season["year"])]
            for season in candidates[:2]:
                advertised = season.get("coverage") or {}
                if not isinstance(advertised.get("fixtures"), dict):
                    continue
                year = season["year"]
                prepare("fixtures", league, year, {})
                mapping = _mapped(session, "api-football", "season", year, f"league:{league['id']}")
                local = session.get(Temporada, mapping.local_id) if mapping else None
                if local and advertised.get("standings") is True:
                    # An annual mapping containing several editions needs review first.
                    phases = session.exec(
                        select(Fase).where(Fase.temporada_id == local.id).limit(2)
                    ).all()
                    if len(phases) <= 1:
                        selection = {"season_id": local.id}
                        if phases:
                            selection["phase_id"] = phases[0].id
                        prepare("standings", league, year, selection)
        _snapshot(
            session,
            "api-football",
            "coverage",
            1,
            scope.selector.get("country", "Colombia"),
            {"competitions": coverage},
        )
        return {"changed": 0, "coverage": coverage, "prepared_profiles": prepared, "topics": []}


class FixturesHandler:
    @staticmethod
    def _metadata(scope):
        from sqlmodel import Session

        from src import database
        from src.sync.models import SyncObservation

        with Session(database.engine) as session:
            last = session.exec(
                select(SyncObservation)
                .where(
                    SyncObservation.scope_id == scope.id,
                    SyncObservation.complete.is_(True),
                )
                .order_by(SyncObservation.last_seen_at.desc())
                .limit(1)
            ).first()
            checkpoint = session.exec(
                select(ProviderSnapshot).where(
                    ProviderSnapshot.provider == "api-football",
                    ProviderSnapshot.entity_type == "league",
                    ProviderSnapshot.local_id == int(scope.selector["league_id"]),
                    ProviderSnapshot.kind == f"metadata:{scope.selector['season']}",
                )
            ).first()
            observations = [row.payload for row in (last, checkpoint) if row]
        for cached in observations:
            try:
                checked = dt.datetime.fromisoformat(cached.get("metadata_checked_at", ""))
                valid = (
                    checked.tzinfo is not None
                    and dt.timedelta() <= dt.datetime.now(dt.UTC) - checked < dt.timedelta(days=1)
                    and cached.get("metadata_key")
                    == [scope.selector.get("league_id"), scope.selector.get("season")]
                    and isinstance(cached.get("league"), dict)
                )
            except (TypeError, ValueError):
                continue
            if valid:
                return {
                    key: cached.get(key)
                    for key in ("league", "teams", "metadata_key", "metadata_checked_at")
                }
        return None

    @staticmethod
    def _checkpoint_metadata(league, year, information):
        """Persist observations only; quota waits must not repeat valid reference calls."""
        from sqlalchemy.exc import IntegrityError
        from sqlmodel import Session

        from src import database

        with Session(database.engine) as session:
            try:
                _snapshot(
                    session, "api-football", "league", league, f"metadata:{year}", information
                )
                session.commit()
            except IntegrityError:
                # Another scope of this league/year can publish the same cache first.
                session.rollback()

    @staticmethod
    def next_interval(session, scope, payload, instant):
        """Fastest allowed configured interval, widened by relevance and shared quota."""
        import math

        from src.sync.models import SyncBudget, SyncScope
        from src.sync.service import effective_api_limits

        fixtures = (payload.get("fixtures") or {}).get("response", [])
        prefix = str(scope.selector.get("round_prefix") or "").strip()
        if prefix:
            fixtures = [
                row
                for row in fixtures
                if str((row.get("league") or {}).get("round", "")).startswith(prefix)
            ]
        live = any(
            ((row.get("fixture") or {}).get("status") or {}).get("short")
            in {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}
            for row in fixtures
        )
        gaps = []
        for row in fixtures:
            try:
                stamp = dt.datetime.fromisoformat(row["fixture"]["date"].replace("Z", "+00:00"))
                if stamp.tzinfo is not None:
                    gaps.append((stamp - instant).total_seconds())
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        if live:
            cadence, horizon = 30, 7200
        elif any(-21600 <= gap <= 900 for gap in gaps):
            cadence, horizon = 300, 21600
        elif any(0 < gap <= 21600 for gap in gaps):
            cadence, horizon = 900, 86400
        elif any(0 < gap <= 172800 for gap in gaps):
            cadence, horizon = 3600, 86400
        elif gaps and all(gap < -86400 for gap in gaps):
            cadence, horizon = 604800, 86400
        else:
            cadence, horizon = 86400, 86400
        plans = session.exec(
            select(SyncScope).where(
                SyncScope.provider == scope.provider, SyncScope.mode != "paused"
            )
        ).all()
        budget = session.get(SyncBudget, scope.provider)
        provider_limit, _ = effective_api_limits(session)
        daily_limit = min(
            provider_limit, min([plan.daily_limit for plan in plans] or [scope.daily_limit])
        )
        used = budget.day_used if budget and budget.day == instant.strftime("%Y-%m-%d") else 0
        # Keep 20% for metadata, reconciliation and recovery. Actual reservations remain atomic.
        available = max(1, math.floor(daily_limit * 0.8) - used)
        floor = math.ceil(horizon * max(1, len(plans)) / available)
        return min(2592000, max(scope.interval_seconds, cadence, math.ceil(floor / 30) * 30))

    def fetch(self, scope, context):
        league, year = _integer(scope.selector, "league_id"), _integer(scope.selector, "season")
        metadata = None if scope.selector.get("existing_only") else self._metadata(scope)

        def call(transport):
            client = APIFootballClient(transport=transport)
            if scope.selector.get("existing_only"):
                return FetchResult({"fixtures": client.fixtures(league, year)})
            information = metadata
            if information is None:
                coverage = client.league(league, year)
                valid = any(
                    (row.get("league") or {}).get("id") == league
                    and (row.get("country") or {}).get("name") == "Colombia"
                    and any(season.get("year") == year for season in row.get("seasons", []))
                    for row in coverage.get("response", [])
                )
                if not valid:
                    raise PermanentError(
                        "La fuente no confirma acceso al torneo y año colombiano seleccionados."
                    )
                information = {
                    "league": coverage,
                    "teams": None,
                    "metadata_key": [league, year],
                    "metadata_checked_at": dt.datetime.now(dt.UTC).isoformat(),
                }
                self._checkpoint_metadata(league, year, information)
            if not isinstance(information.get("teams"), dict):
                teams = client.teams(league, year)
                if (teams.get("paging") or {}).get("total", 1) > 1 or teams.get(
                    "results", len(teams.get("response", []))
                ) != len(teams.get("response", [])):
                    raise PermanentError(
                        "El catálogo de equipos llegó incompleto; se conserva el avance para reintentarlo."
                    )
                information = {**information, "teams": teams}
                self._checkpoint_metadata(league, year, information)
            fixtures = client.fixtures(league, year)
            complete = (fixtures.get("paging") or {}).get("total", 1) <= 1 and fixtures.get(
                "results", len(fixtures.get("response", []))
            ) == len(fixtures.get("response", []))
            return FetchResult({**information, "fixtures": fixtures}, complete=complete)

        return _fetch(call, context)

    def apply(self, session, scope, payload, context):
        selector = scope.selector
        league_id, year = _integer(selector, "league_id"), _integer(selector, "season")
        annual_layout = _annual_women_layout(
            league_id, year, payload["fixtures"].get("response", [])
        )
        if (
            not annual_layout
            and not selector.get("round_prefix")
            and not selector.get("existing_only")
        ):
            rows = payload["fixtures"].get("response", [])
            prefixes = {}
            unclassified = []
            for row in rows:
                round_name = str((row.get("league") or {}).get("round", ""))
                match = re.match(
                    r"^(Apertura|Clausura|Finalizaci[oó]n|Championship)\b",
                    round_name,
                    re.IGNORECASE,
                )
                prefix = match[1] if match else None
                # Verified API 240 / 2022 response publishes a two-leg promotion
                # final in addition to Apertura, Clausura and Championship.
                # Its exact label is a separate annual playoff, never an edition
                # alias. Unknown years, leagues or further playoff rounds remain
                # subject to review instead of inheriting this historical policy.
                if (
                    league_id == 240
                    and year == 2022
                    and round_name == "Promotion Play-offs - Final"
                ):
                    prefix = "Promotion Play-offs"
                if prefix:
                    prefixes.setdefault(prefix, []).append(row)
                else:
                    unclassified.append(row)
            if prefixes and not selector.get("season_id") and not unclassified:
                editions = []
                for prefix, selected_rows in prefixes.items():
                    selected_scope = SimpleNamespace(**scope.model_dump())
                    selected_scope.selector = {
                        **selector,
                        "round_prefix": prefix,
                        "season_id": (selector.get("season_ids") or {}).get(prefix),
                    }
                    selected_payload = {
                        **payload,
                        "fixtures": {**payload["fixtures"], "response": selected_rows},
                    }
                    editions.append(self.apply(session, selected_scope, selected_payload, context))
                return {
                    "changed": sum(row.get("changed", 0) for row in editions),
                    "created": sum(row.get("created", 0) for row in editions),
                    "updated": sum(row.get("updated", 0) for row in editions),
                    "skipped": [item for row in editions for item in row.get("skipped", [])],
                    "season_ids": [row["season_id"] for row in editions if row.get("season_id")],
                    "editions": editions,
                    "requires_review": any(row.get("requires_review") for row in editions),
                    "topics": sorted(
                        {topic for row in editions for topic in row.get("topics", [])}
                    ),
                }
        if selector.get("existing_only"):
            selected = dict(payload["fixtures"])
            prefix = str(selector.get("round_prefix") or "").strip()
            if not prefix:
                mapping = session.exec(
                    select(ProviderMapping).where(
                        ProviderMapping.provider == "api-football",
                        ProviderMapping.entity_type == "season",
                        ProviderMapping.local_id == _integer(selector, "season_id"),
                        ProviderMapping.external_id == str(year),
                    )
                ).first()
                if mapping and ":edition:" in mapping.external_scope:
                    prefix = mapping.external_scope.split(":edition:", 1)[1]
            if prefix:
                selected["response"] = [
                    row
                    for row in selected.get("response", [])
                    if str((row.get("league") or {}).get("round", "")).startswith(prefix)
                ]
            elif not annual_layout and any(
                word in str((row.get("league") or {}).get("round", "")).lower()
                for row in selected.get("response", [])
                for word in ("apertura", "clausura", "finalizacion", "finalización")
            ):
                issue(
                    session,
                    scope.id,
                    "edition_selection",
                    "Selecciona el torneo dentro del año externo antes de actualizar esta edición.",
                )
                return {"changed": 0, "requires_review": True}
            return sync_competition_fixtures(
                session,
                _integer(selector, "competition_id"),
                _integer(selector, "season_id"),
                selected,
                commit=False,
                context=context,
            )
        leagues = payload["league"].get("response", [])
        raw = next(
            (row for row in leagues if (row.get("league") or {}).get("id") == league_id), None
        )
        if raw is None or not any(s.get("year") == year for s in raw.get("seasons", [])):
            raise PermanentError("La fuente no confirma cobertura para la edición elegida.")
        league, country = raw["league"], raw.get("country") or {}
        if country.get("name") != "Colombia":
            raise PermanentError("Este piloto está configurado para competiciones colombianas.")
        competition, catalog_changed = _identity(
            session,
            scope,
            "competition",
            league_id,
            {
                "nombre": league["name"],
                "logo": "",
                "pais": "Colombia",
                "tipo": TipoCompeticion.COPA_NACIONAL
                if league.get("type") == "Cup"
                else TipoCompeticion.LIGA_NACIONAL,
            },
            context=context,
            target_id=selector.get("competition_id"),
        )
        if competition is None:
            return {"changed": 0, "topics": [], "requires_review": True}
        catalog_changed += _api_metadata(session, "competition", competition, raw, context)
        prefix = selector.get("round_prefix", "").strip()
        if (
            not prefix
            and not annual_layout
            and any(
                word in str((row.get("league") or {}).get("round", "")).lower()
                for row in payload["fixtures"].get("response", [])
                for word in ("apertura", "clausura", "finalizacion", "finalización")
            )
        ):
            issue(
                session,
                scope.id,
                "edition_selection",
                "Esta temporada externa contiene torneos diferentes. Selecciona el torneo por su prefijo de ronda para mantenerlos separados.",
            )
            return {"changed": catalog_changed, "topics": ["catalog"], "requires_review": True}
        external_scope = f"league:{league_id}" + (f":edition:{prefix}" if prefix else "")
        published_season = next(row for row in raw["seasons"] if row.get("year") == year)
        season_values = {
            "competicion_id": competition.id,
            "nombre": selector.get("edition_name") or f"{year} {prefix}".strip(),
            "activa": published_season.get("current") is True,
        }
        # Annual metadata cannot provide the dates of an independently selected sub-edition.
        if not prefix:
            for key, field in (("start", "fecha_inicio"), ("end", "fecha_fin")):
                if published_season.get(key):
                    try:
                        season_values[field] = dt.date.fromisoformat(published_season[key])
                    except (TypeError, ValueError) as exc:
                        raise PermanentError(
                            "La fuente publica fechas de temporada no válidas."
                        ) from exc
        season_target = selector.get("season_id")
        if not season_target and prefix.lower() in {
            "apertura",
            "clausura",
            "finalizacion",
            "finalización",
        }:
            archive_edition = "Apertura" if prefix.lower() == "apertura" else "Clausura"
            archive = _mapped(
                session,
                "openfootball",
                "season",
                f"{year}/{archive_edition}",
                "colombia/primera-a",
            )
            if archive:
                from src.models import Temporada

                candidate = session.get(Temporada, archive.local_id)
                if candidate and candidate.competicion_id == competition.id:
                    season_target = candidate.id
        season, count = _identity(
            session,
            scope,
            "season",
            year,
            season_values,
            external_scope=external_scope,
            context=context,
            target_id=season_target,
        )
        catalog_changed += count
        if season is None:
            return {"changed": catalog_changed, "topics": ["catalog"], "requires_review": True}
        for raw_team in payload["teams"].get("response", []):
            team = raw_team.get("team") or {}
            if not team.get("id") or not team.get("name") or team.get("national"):
                continue
            local, count = _identity(
                session,
                scope,
                "team",
                team["id"],
                {"nombre": team["name"], "logo": "", "pais": "Colombia", "tipo": TipoEquipo.CLUB},
                context=context,
                target_id=(selector.get("team_ids") or {}).get(str(team["id"])),
            )
            catalog_changed += count
            if local:
                catalog_changed += _api_metadata(session, "team", local, raw_team, context)
                if not session.get(Participacion, (local.id, competition.id)):
                    session.add(Participacion(equipo_id=local.id, competicion_id=competition.id))
                    catalog_changed += 1
        fixtures = dict(payload["fixtures"])
        if prefix:
            fixtures["response"] = [
                row
                for row in fixtures["response"]
                if str((row.get("league") or {}).get("round", "")).startswith(prefix)
            ]
        result = sync_competition_fixtures(
            session, competition.id, season.id, fixtures, commit=False, context=context
        )
        result["changed"] += catalog_changed
        if catalog_changed:
            result["topics"] = sorted(set(result.get("topics", [])) | {"catalog"})
        for skipped in result["skipped"]:
            issue(
                session,
                scope.id,
                f"fixture:{skipped['fixture_id']}",
                f"Partido {skipped['fixture_id']}: {skipped['reason']}. Revisa las identidades vinculadas.",
            )
        return result


class DetailHandler:
    def fetch(self, scope, context):
        fixture = _integer(scope.selector, "fixture_id")

        def call(transport):
            client = APIFootballClient(transport=transport)
            result = {
                "events": client.fixture_events(fixture),
                "lineups": client.fixture_lineups(fixture),
                "statistics": client.fixture_statistics(fixture),
            }
            for value in result.values():
                value["_complete"] = (
                    bool(value.get("response"))
                    and value.get("results") == len(value["response"])
                    and (value.get("paging") or {}).get("total", 1) == 1
                )
            return FetchResult(result)

        return _fetch(call, context)

    def apply(self, session, scope, payload, context):
        return sync_match_detail(
            session,
            _integer(scope.selector, "match_id"),
            events_payload=payload["events"],
            lineups_payload=payload["lineups"],
            statistics_payload=payload["statistics"],
            commit=False,
            context=context,
        )


class StandingsHandler:
    def fetch(self, scope, context):
        return _fetch(
            lambda transport: FetchResult(
                APIFootballClient(transport=transport).standings(
                    _integer(scope.selector, "league_id"), _integer(scope.selector, "season")
                )
            ),
            context,
        )

    def apply(self, session, scope, payload, context):
        from src.football.projections import (
            StandingsScopeError,
            scope_key,
            store_official_standings,
            validate_scope,
        )
        from src.models import Fase, Grupo

        season_id = _integer(scope.selector, "season_id")
        phase_id = _integer(scope.selector, "phase_id") if scope.selector.get("phase_id") else None
        group_id = _integer(scope.selector, "group_id") if scope.selector.get("group_id") else None
        try:
            season = validate_scope(session, season_id, phase_id, group_id)
        except StandingsScopeError as exc:
            raise PermanentError(str(exc)) from exc
        mapping = _mapped(
            session, "api-football", "competition", _integer(scope.selector, "league_id")
        )
        if not mapping or mapping.local_id != season.competicion_id:
            raise PermanentError("La tabla no corresponde a la edición local seleccionada.")
        if (
            not phase_id
            and session.exec(select(Fase.id).where(Fase.temporada_id == season_id).limit(1)).first()
        ):
            raise PermanentError("Selecciona la fase de esta clasificación para no mezclar tablas.")
        if (
            phase_id
            and not group_id
            and session.exec(select(Grupo.id).where(Grupo.fase_id == phase_id).limit(1)).first()
        ):
            raise PermanentError("Selecciona el grupo de esta clasificación.")
        response = payload.get("response")
        if not isinstance(response, list) or not response:
            raise RetryableError("La fuente todavía no devuelve una clasificación.")
        if len(response) != 1:
            raise PermanentError("La respuesta de clasificación contiene varias competiciones.")
        league = response[0].get("league") or {}
        if league.get("id") != int(scope.selector["league_id"]) or league.get("season") != int(
            scope.selector["season"]
        ):
            raise PermanentError("La clasificación recibida pertenece a otro ámbito.")
        tables = league.get("standings")
        if not isinstance(tables, list) or not tables:
            raise RetryableError("La fuente todavía no devuelve una tabla completa.")
        candidates = []
        for table in tables:
            if (
                not isinstance(table, list)
                or not table
                or any(not isinstance(row, dict) for row in table)
            ):
                raise PermanentError("La estructura de la tabla externa no es válida.")
            grouped = {}
            for row in table:
                label = str(row.get("group") or "").strip()
                grouped.setdefault(label, []).append(row)
            candidates.extend(grouped.items())
        table_name = str(scope.selector.get("table_name") or "").strip()
        if table_name:
            candidates = [(name, rows) for name, rows in candidates if name == table_name]
        if len(candidates) != 1:
            raise PermanentError(
                "La fuente publica varias tablas o no encuentra la elegida. Indica el nombre exacto de la tabla."
            )
        selected_name, selected = candidates[0]
        external_ids = [str((row.get("team") or {}).get("id")) for row in selected]
        links = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "api-football",
                ProviderMapping.entity_type == "team",
                ProviderMapping.external_scope == "",
                ProviderMapping.external_id.in_(external_ids),
            )
        ).all()
        teams = {row.external_id: row.local_id for row in links}
        normalized = []
        for row, external_id in zip(selected, external_ids, strict=True):
            if external_id not in teams:
                raise PermanentError(
                    "La clasificación incluye equipos sin identidad canónica verificada."
                )
            stats = row.get("all") or {}
            goals = stats.get("goals") or {}
            normalized.append(
                {
                    "team_id": teams[external_id],
                    "rank": row.get("rank"),
                    "points": row.get("points"),
                    "played": stats.get("played"),
                    "won": stats.get("win"),
                    "drawn": stats.get("draw"),
                    "lost": stats.get("lose"),
                    "goals_for": goals.get("for"),
                    "goals_against": goals.get("against"),
                    "goal_difference": row.get("goalsDiff"),
                    "source_group": selected_name,
                }
            )
        key = scope_key(season_id, phase_id, group_id)
        previous = session.exec(
            select(OfficialStandingSnapshot)
            .where(
                OfficialStandingSnapshot.scope_key == key,
                OfficialStandingSnapshot.source == "api-football",
            )
            .order_by(
                OfficialStandingSnapshot.fetched_at.desc(), OfficialStandingSnapshot.id.desc()
            )
            .limit(1)
        ).first()
        previous_id = previous.id if previous else None
        try:
            snapshot = store_official_standings(
                session,
                season_id=season_id,
                phase_id=phase_id,
                group_id=group_id,
                source="api-football",
                source_url="https://www.api-football.com/documentation-v3#tag/Standings",
                rows=normalized,
                observed_at=getattr(context, "observed_at", None),
            )
        except StandingsScopeError as exc:
            raise PermanentError(str(exc)) from exc
        session.flush()
        changed = snapshot.id != previous_id
        if changed:
            record_change(
                session,
                entity_type="season",
                entity_id=season_id,
                field="tabla_fuente",
                before={"snapshot_id": previous_id} if previous_id else None,
                after={"snapshot_id": snapshot.id, "scope_key": key, "source_group": selected_name},
                action="source_standings",
                actor="service:sync",
                reason="Clasificación publicada por la fuente",
                version=snapshot.id,
                source="api-football",
                run_id=getattr(context, "job_id", None),
            )
        return {"changed": int(changed), "topics": ["standings"]}


def register_handlers(registry):
    from src.providers.api_batch import BatchDetailsHandler
    from src.providers.api_standings import BatchStandingsHandler
    from src.providers.openfootball import OpenFootballHandler

    registry[("openfootball", "archive")] = OpenFootballHandler()
    registry.update(
        {
            ("wikidata", "catalog"): CatalogHandler(),
            ("wikidata", "history"): EnrichmentHandler(),
            ("wikidata", "media"): EnrichmentHandler(media=True),
            ("api-football", "discovery"): DiscoveryHandler(),
            ("api-football", "fixtures"): FixturesHandler(),
            ("api-football", "detail"): DetailHandler(),
            ("api-football", "details_batch"): BatchDetailsHandler(),
            ("api-football", "standings"): StandingsHandler(),
            ("api-football", "standings_batch"): BatchStandingsHandler(),
        }
    )


def validate_scope_config(provider, kind, selector):
    if provider == "openfootball" and kind == "archive":
        from src.providers.openfootball import validate_selector

        return validate_selector(selector)
    available = {
        "wikidata": {"catalog", "media", "history"},
        "api-football": {
            "discovery",
            "fixtures",
            "detail",
            "details_batch",
            "standings",
            "standings_batch",
        },
    }
    if kind not in available.get(provider, set()):
        raise ValueError("La fuente no ofrece ese tipo de actualización.")
    selector = dict(selector)
    required = {
        "fixtures": ("league_id", "season"),
        "standings": ("league_id", "season", "season_id"),
        "detail": ("match_id", "fixture_id"),
        "details_batch": ("league_id", "season"),
        "standings_batch": ("league_id", "season"),
        "media": ("local_id",),
        "history": ("local_id",),
    }
    try:
        for key in required.get(kind, ()):
            selector[key] = _integer(selector, key)
    except PermanentError as exc:
        raise ValueError(str(exc)) from exc
    if "season" in selector and not 1900 <= selector["season"] <= dt.date.today().year + 2:
        raise ValueError("El año de la temporada no es válido.")
    if kind == "catalog":
        selector.setdefault("collection", "colombia")
        if selector["collection"] not in COLLECTIONS:
            raise ValueError("Elige una colección disponible.")
    if kind in {"media", "history"}:
        from src.providers.wikidata import QID_PATTERN

        selector["qid"] = str(selector.get("qid", "")).upper()
        if not QID_PATTERN.fullmatch(selector["qid"]) or selector.get("entity_type") not in {
            "team",
            "competition",
            "confederation",
        }:
            raise ValueError("Elige una ficha e identidad de Wikidata válidas.")
    if kind == "discovery":
        if selector.get("country", "Colombia") != "Colombia":
            raise ValueError("Este piloto descubre competiciones de Colombia.")
        selector["country"] = "Colombia"
    if len(str(selector.get("round_prefix", ""))) > 120:
        raise ValueError("El nombre de la ronda es demasiado largo.")
    if kind == "fixtures":
        for field, maximum in (("team_ids", 100), ("season_ids", 10)):
            links = selector.get(field, {})
            if not isinstance(links, dict) or len(links) > maximum:
                raise ValueError("Las identidades revisadas no tienen un formato válido.")
            for external, local in links.items():
                if not isinstance(external, str) or type(local) is not int or local <= 0:
                    raise ValueError(
                        "Cada vínculo requiere una identidad externa y una ficha local."
                    )
                if field == "team_ids" and (not external.isdigit() or int(external) <= 0):
                    raise ValueError("Los identificadores externos de equipos deben ser numéricos.")
    return selector
