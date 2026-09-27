import assert from "node:assert/strict";
import test from "node:test";
import {
  filterMatches,
  formatMatchDate,
  sortMatches,
} from "./public/matchFilters.js";

const matches = [
  {
    id: 4,
    estado: "finalizado",
    competicion_id: 2,
    fecha: "2026-09-20T20:00:00Z",
  },
  {
    id: 3,
    estado: "programado",
    competicion_id: 1,
    fecha: "2026-09-29T20:00:00Z",
  },
  {
    id: 2,
    estado: "programado",
    competicion_id: 2,
    fecha: "2026-09-28T20:00:00Z",
  },
  {
    id: 1,
    estado: "en vivo",
    competicion_id: 1,
    fecha: "2026-09-26T20:00:00Z",
  },
];
test("live games lead, followed by scheduled games in chronological order", () => {
  assert.deepEqual(
    sortMatches(matches).map((m) => m.id),
    [1, 2, 3, 4],
  );
  assert.deepEqual(
    matches.map((m) => m.id),
    [4, 3, 2, 1],
  );
});
test("status and competition filters combine and accept select string values", () => {
  assert.deepEqual(
    filterMatches(matches, "programado", "2").map((m) => m.id),
    [2],
  );
  assert.deepEqual(filterMatches(matches, "en vivo", "2"), []);
  assert.equal(filterMatches(matches).length, 4);
});
test("missing or invalid match dates have a readable fallback", () => {
  assert.equal(formatMatchDate(null), "Fecha por confirmar");
  assert.equal(formatMatchDate("invalid"), "Fecha por confirmar");
  assert.ok(formatMatchDate("2026-09-26T20:00:00Z").includes("2026"));
});
test("scheduled matches without a date do not precede known upcoming fixtures", () => {
  const undated = { id: 5, estado: "programado", fecha: null };
  assert.deepEqual(
    filterMatches([...matches, undated], "programado").map((m) => m.id),
    [2, 3, 5],
  );
});
