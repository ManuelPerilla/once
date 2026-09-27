"""Wikidata observations -> reviewed identity reconciliation -> ONCE catalog.

No HTTP framework dependency, automatic enrollment, image copying or source IDs
as primary keys. Each application is atomic and repeatable.
"""

import datetime as dt
import hashlib
import json
import threading
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import text
from sqlmodel import Session, select

from src.models import (
    CatalogImportBatch,
    Competicion,
    Confederacion,
    Equipo,
    ProviderMapping,
    ProviderSnapshot,
)
from src.providers import WikidataClient

from .collections import COLLECTIONS
from .schemas import ImportDecision

MODELS = {"confederation": Confederacion, "competition": Competicion, "team": Equipo}
CACHE_HOURS = 24
LOCK = threading.Lock()


class CatalogError(ValueError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc)


def _lock(session):
    # Serialize catalog writers across API workers, not just Python threads.
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(726623014)"))


def _key(value):
    return " ".join(
        "".join(
            char if char.isalnum() else " "
            for char in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(char)
        ).split()
    )


def _claim_ids(entity, prop):
    return {
        value.get("id")
        for statement in entity.get("claims", {}).get(prop, [])
        if statement.get("rank") != "deprecated"
        and isinstance(
            value := statement.get("mainsnak", {}).get("datavalue", {}).get("value"), dict
        )
    }


def normalize(spec, entity):
    labels = entity.get("labels", {})
    name = spec.get("preferred_name") or (labels.get("es") or labels.get("en") or {}).get("value")
    errors = []
    if "missing" in entity or entity.get("id") != spec["qid"] or not name:
        errors.append("La fuente no devuelve una identidad completa y estable.")
    if "Q2736" not in _claim_ids(entity, "P641"):
        errors.append("La fuente no confirma que la entidad esté vinculada al fútbol.")
    if spec.get("country_qid") and spec["country_qid"] not in _claim_ids(entity, "P17"):
        errors.append("El país de la fuente no coincide con el de esta colección.")
    aliases = {name} if name else set()
    aliases.update(label["value"] for label in labels.values() if label.get("value"))
    for language in ("es", "en"):
        aliases.update(
            item["value"]
            for item in entity.get("aliases", {}).get(language, [])
            if item.get("value")
        )
    return {
        **spec,
        "nombre": name or spec["qid"],
        "aliases": sorted(aliases),
        "description": (entity.get("descriptions", {}).get("es") or {}).get("value", ""),
        "source_url": f"https://www.wikidata.org/wiki/{spec['qid']}",
        "source_revision": entity.get("lastrevid"),
        "license": "CC0-1.0",
        "errors": errors,
    }


def _compatible(local, row):
    if row["entity_type"] == "confederation":
        return True
    return local.tipo == row["tipo"] and _key(local.pais) == _key(row["pais"])


def preview(session: Session, batch: CatalogImportBatch, cached=True):
    maps = session.exec(select(ProviderMapping).where(ProviderMapping.provider == "wikidata")).all()
    external = {(m.entity_type, m.external_id): m for m in maps}
    mapped_local = {(m.entity_type, m.local_id): m.external_id for m in maps}
    local = {kind: session.exec(select(model)).all() for kind, model in MODELS.items()}
    rows = []
    for row in batch.payload["rows"]:
        kind = row["entity_type"]
        mapping = external.get((kind, row["qid"]))
        current = next(
            (item for item in local[kind] if mapping and item.id == mapping.local_id), None
        )
        errors = list(row["errors"])
        if mapping and not current:
            errors.append("El vínculo apunta a una entidad local eliminada. Revisa el mapping.")
        candidates, choices = [], []
        names = [_key(alias) for alias in row["aliases"]]
        for item in local[kind]:
            if not _compatible(item, row):
                continue
            other_qid = mapped_local.get((kind, item.id))
            if other_qid and other_qid != row["qid"]:
                continue
            choices.append({"id": item.id, "nombre": item.nombre})
            local_name = _key(item.nombre)
            score = max(
                (SequenceMatcher(None, local_name, alias).ratio() for alias in names), default=0
            )
            # Commercial suffixes often differ (Liga BetPlay / Liga BetPlay Dimayor).
            # A prefix is only a suggestion; it never merges identities automatically.
            if (
                len(local_name) >= 10
                and len(local_name.split()) >= 2
                and any(alias.startswith(local_name + " ") for alias in names)
            ):
                score = max(score, 0.85)
            if score >= 0.82:
                candidates.append({"id": item.id, "nombre": item.nombre, "exact": score == 1})
        status = "blocked" if errors else "linked" if current else "review" if candidates else "new"
        rows.append(
            {
                **row,
                "errors": errors,
                "status": status,
                "local_id": current.id if current else None,
                "local_name": current.nombre if current else None,
                "candidates": candidates,
                "choices": choices,
            }
        )
    return {
        "id": batch.id,
        "collection": batch.collection,
        "name": COLLECTIONS[batch.collection]["name"],
        "fetched_at": batch.fetched_at,
        "cached": cached,
        "cache_hours": CACHE_HOURS,
        "rows": rows,
        "last_result": batch.last_result,
    }


def prepare(session: Session, collection: str, client=None, *, interactive=False):
    definition = COLLECTIONS.get(collection)
    if not definition:
        raise CatalogError("Colección desconocida.")
    digest = hashlib.sha256(json.dumps(definition["entries"], sort_keys=True).encode()).hexdigest()
    with LOCK:
        _lock(session)
        latest = session.exec(
            select(CatalogImportBatch)
            .where(
                CatalogImportBatch.collection == collection,
                CatalogImportBatch.fetched_at >= now() - dt.timedelta(hours=CACHE_HOURS),
            )
            .order_by(CatalogImportBatch.fetched_at.desc())
        ).first()
        if latest and latest.payload.get("definition") == digest:
            result = preview(session, latest)
            session.commit()  # Release the transaction lock even on a cache hit.
            return result
        entries = definition["entries"]
        entities = (client or WikidataClient()).entities(
            [entry["qid"] for entry in entries], interactive=interactive
        )
        batch = CatalogImportBatch(
            collection=collection,
            payload={
                "definition": digest,
                "entities": entities,
                "rows": [normalize(entry, entities.get(entry["qid"], {})) for entry in entries],
            },
        )
        session.add(batch)
        session.flush()
        result = preview(session, batch, cached=False)
        session.commit()
        return result


def _snapshot(session, batch, row, local_id):
    existing = session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == "wikidata",
            ProviderSnapshot.entity_type == row["entity_type"],
            ProviderSnapshot.local_id == local_id,
            ProviderSnapshot.kind == "catalog_identity",
        )
    ).first()
    snapshot = existing or ProviderSnapshot(
        provider="wikidata",
        entity_type=row["entity_type"],
        local_id=local_id,
        kind="catalog_identity",
        payload={},
    )
    snapshot.fetched_at = batch.fetched_at
    snapshot.payload = {
        "source_url": row["source_url"],
        "license": row["license"],
        "import_batch_id": batch.id,
        "classification": row,
        "entity": batch.payload["entities"][row["qid"]],
    }
    session.add(snapshot)


def apply(session: Session, batch_id: str, decisions: list[ImportDecision]):
    with LOCK:
        try:
            _lock(session)
            batch = session.get(CatalogImportBatch, batch_id)
            if not batch:
                raise CatalogError("No se encontró el lote. Prepara la colección de nuevo.")
            if batch.fetched_at < now() - dt.timedelta(hours=CACHE_HOURS):
                raise CatalogError("El lote ha caducado. Prepara una vista previa actualizada.")
            plan = preview(session, batch)
            rows = {row["qid"]: row for row in plan["rows"]}
            selected = {decision.qid: decision for decision in decisions}
            if len(selected) != len(decisions) or not set(selected).issubset(rows):
                raise CatalogError(
                    "La selección contiene identificadores repetidos o ajenos al lote."
                )
            results = {
                "created": 0,
                "linked": 0,
                "reused": 0,
                "skipped": 0,
                "items": [],
                "applied_at": now().isoformat(),
            }
            resolved = {
                qid: row["local_id"] for qid, row in rows.items() if row["status"] == "linked"
            }
            used_targets = set()
            for row in plan["rows"]:  # Dependencies precede teams/competitions in every collection.
                qid, kind = row["qid"], row["entity_type"]
                choice = selected.get(qid)
                if not choice or choice.action == "skip":
                    results["skipped"] += 1
                    continue
                if row["status"] == "blocked":
                    raise CatalogError(f"{row['nombre']}: {' '.join(row['errors'])}")
                if row["status"] == "linked":
                    if choice.action == "link" and choice.local_id != row["local_id"]:
                        raise CatalogError("La entidad ya está vinculada a otro registro local.")
                    results["reused"] += 1
                    _snapshot(session, batch, row, row["local_id"])
                    continue
                if row["status"] != choice.expected_status:
                    raise CatalogError(
                        "El catálogo cambió desde la vista previa. Prepara la colección otra vez."
                    )
                conf_qid = row.get("confederation_qid")
                conf_id = resolved.get(conf_qid) if conf_qid else None
                if conf_qid and not conf_id:
                    raise CatalogError(
                        "Incluye o vincula CONMEBOL antes de importar sus equipos y competiciones."
                    )
                if choice.action == "link":
                    if choice.local_id not in {item["id"] for item in row["choices"]}:
                        raise CatalogError(
                            "El vínculo elegido no es compatible o ya pertenece a otra identidad."
                        )
                    target = (kind, choice.local_id)
                    if target in used_targets:
                        raise CatalogError(
                            "Dos identidades diferentes no pueden vincularse al mismo registro."
                        )
                    used_targets.add(target)
                    item = session.get(MODELS[kind], choice.local_id)
                    if conf_qid and item.confederacion_id != conf_id:
                        raise CatalogError(
                            f"{item.nombre}: la confederación local no coincide. Revisa el catálogo."
                        )
                    results["linked"] += 1
                else:
                    if choice.local_id is not None:
                        raise CatalogError("Una creación no debe indicar un ID local.")
                    # Avoid two creates with the same identity in this transaction.
                    if any(
                        _key(item.nombre) == _key(row["nombre"]) and _compatible(item, row)
                        for item in session.exec(select(MODELS[kind])).all()
                    ):
                        raise CatalogError(
                            f"Ya existe {row['nombre']}. Vincula el registro existente."
                        )
                    values = {"nombre": row["nombre"], "logo": ""}
                    if kind != "confederation":
                        values.update(tipo=row["tipo"], pais=row["pais"], confederacion_id=conf_id)
                    item = MODELS[kind](**values)
                    session.add(item)
                    session.flush()
                    results["created"] += 1
                resolved[qid] = item.id
                session.add(
                    ProviderMapping(
                        provider="wikidata",
                        entity_type=kind,
                        local_id=item.id,
                        external_id=qid,
                        source_url=row["source_url"],
                        verified_at=now(),
                    )
                )
                _snapshot(session, batch, row, item.id)
                results["items"].append({"qid": qid, "entity_type": kind, "local_id": item.id})
                session.flush()
            batch.last_result = results
            session.add(batch)
            session.commit()
            return results
        except Exception:
            session.rollback()
            raise
