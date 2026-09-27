import assert from "node:assert/strict";
import { test } from "node:test";
import {
  accountLabel,
  coverageLabels,
  sortedSeasons,
} from "./admin/footballConnection.js";

test("a configured credential alone does not claim verified account access", () => {
  assert.equal(accountLabel(null), "Consultando configuración");
  assert.equal(accountLabel({ configured: false }), "Pendiente de conectar");
  assert.match(accountLabel({ configured: true }), /falta comprobar/);
  assert.equal(
    accountLabel({ configured: true, account: { active: false } }),
    "Cuenta sin acceso activo",
  );
  assert.equal(
    accountLabel({
      configured: true,
      state: "connected",
      account: { active: true },
    }),
    "Cuenta comprobada",
  );
  assert.equal(
    accountLabel({
      configured: true,
      state: "error",
      account: { active: true },
    }),
    "La última comprobación falló",
  );
});

test("coverage labels only announce features explicitly reported by the source", () => {
  assert.deepEqual(coverageLabels(), []);
  assert.deepEqual(
    coverageLabels({
      standings: true,
      fixtures: { events: true, lineups: false, statistics_players: "true" },
    }),
    ["Clasificaciones", "Jugadas"],
  );
});

test("available seasons remain explicit years and are displayed newest first", () => {
  const original = [
    { year: 2024 },
    { year: 2026, current: true },
    { year: "2025" },
    {},
  ];
  assert.deepEqual(
    sortedSeasons(original).map((season) => season.year),
    [2026, 2024],
  );
  assert.equal(original[0].year, 2024);
});

test("a verified account season range hides advertised years that its plan cannot access", () => {
  const published = [
    { year: 2022 },
    { year: 2024 },
    { year: 2025 },
    { year: 2026 },
  ];
  assert.deepEqual(
    sortedSeasons(published, [2022, 2023, 2024]).map((season) => season.year),
    [2024, 2022],
  );
  assert.deepEqual(sortedSeasons(published, []), []);
  assert.equal(sortedSeasons(published, null).length, 4);
  assert.equal(sortedSeasons(published, ["2024"]).length, 4);
});
