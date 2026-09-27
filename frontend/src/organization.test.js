import test from "node:test";
import assert from "node:assert/strict";
import {
  EMPTY_MATCH_FILTERS,
  changeMatchContext,
  filterMatches,
  filterEnrollments,
} from "./admin/organization.js";

const matches = [
  {
    id: 1,
    competicion_id: 1,
    temporada_id: 11,
    fase_id: 21,
    equipo_local_id: 1,
    equipo_visitante_id: 2,
    equipo_local: { nombre: "Atlético" },
    equipo_visitante: { nombre: "Norte" },
    competicion: { nombre: "Liga" },
    estado: "finalizado",
    fecha: "2025-01-10T12:00:00",
    jornada: "Final",
  },
  {
    id: 2,
    competicion_id: 1,
    temporada_id: 12,
    fase_id: 22,
    estado: "programado",
    fecha: "2026-01-10T12:00:00",
  },
  {
    id: 3,
    competicion_id: 2,
    temporada_id: null,
    estado: "programado",
    fecha: null,
  },
];
test("match context isolates seasons and searches names without accents", () => {
  assert.deepEqual(
    filterMatches(matches, {
      ...EMPTY_MATCH_FILTERS,
      competition: "1",
      season: "11",
      search: "atletico",
    }).map((x) => x.id),
    [1],
  );
  assert.deepEqual(
    filterMatches(matches, {
      ...EMPTY_MATCH_FILTERS,
      season: "unassigned",
    }).map((x) => x.id),
    [3],
  );
});
test("parent filter changes clear dependent choices only", () => {
  const filters = {
    ...EMPTY_MATCH_FILTERS,
    competition: "1",
    season: "11",
    phase: "21",
    team: "2",
    search: "norte",
  };
  assert.deepEqual(changeMatchContext(filters, "competition", "2"), {
    ...filters,
    competition: "2",
    season: "",
    phase: "",
    team: "",
  });
  assert.equal(changeMatchContext(filters, "season", "12").phase, "");
  assert.equal(filters.phase, "21");
});
test("date filters are inclusive and exclude unscheduled dates, with stable ordering", () => {
  assert.deepEqual(
    filterMatches(matches, {
      ...EMPTY_MATCH_FILTERS,
      from: "2025-01-10",
      to: "2025-01-10",
    }).map((x) => x.id),
    [1],
  );
  assert.deepEqual(
    filterMatches(matches, { ...EMPTY_MATCH_FILTERS, sort: "oldest" }).map(
      (x) => x.id,
    ),
    [1, 2, 3],
  );
  assert.deepEqual(
    filterMatches(matches, {
      ...EMPTY_MATCH_FILTERS,
      from: "2026-02-01",
      to: "2026-01-01",
    }),
    [],
  );
});
test("enrollment filters respect participation and do not infer seasons", () => {
  const teams = [
    { id: 1, nombre: "Águilas", tipo: "club", competiciones: [{ id: 5 }] },
    { id: 2, nombre: "Norte", tipo: "seleccion", competiciones: [] },
  ];
  assert.deepEqual(
    filterEnrollments(teams, { competition: "5", search: "agui" }).map(
      (x) => x.id,
    ),
    [1],
  );
  assert.deepEqual(
    filterEnrollments(teams, { state: "free" }).map((x) => x.id),
    [2],
  );
  assert.deepEqual(
    filterEnrollments(teams, { competition: "5", state: "free" }),
    [],
  );
});
