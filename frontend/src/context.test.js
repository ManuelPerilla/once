import assert from "node:assert/strict";
import { test } from "node:test";
import {
  changeContextFilter,
  contextPayload,
  emptyContextFilters,
  filterContext,
} from "./admin/context/selectors.js";

const data = {
  competiciones: [
    { id: 1, nombre: "Liga de Bogotá" },
    { id: 2, nombre: "Copa Nacional" },
  ],
  temporadas: [
    { id: 10, competicion_id: 1, nombre: "2026", activa: true },
    { id: 20, competicion_id: 2, nombre: "2026", activa: false },
  ],
  fases: [
    { id: 101, temporada_id: 10, nombre: "Jornada 10", orden: 10 },
    { id: 102, temporada_id: 10, nombre: "Jornada 2", orden: 2 },
    { id: 201, temporada_id: 20, nombre: "Final", orden: 1 },
  ],
};
const run = (module, filters = {}, records = data[module]) =>
  filterContext(
    module,
    records,
    { ...emptyContextFilters(), ...filters },
    data,
  );

test("changing a parent clears only its dependent context filter", () => {
  const filters = {
    ...emptyContextFilters(),
    competition: "1",
    season: "10",
    country: "Colombia",
    city: "Bogotá",
    search: "liga",
  };
  assert.deepEqual(changeContextFilter(filters, "competition", "2"), {
    ...filters,
    competition: "2",
    season: "",
  });
  assert.deepEqual(changeContextFilter(filters, "country", "España"), {
    ...filters,
    country: "España",
    city: "",
  });
  assert.equal(filters.season, "10");
});

test("phase hierarchy never mixes same-named seasons from different competitions", () => {
  assert.deepEqual(
    run("fases", { competition: "1" }).map((item) => item.id),
    [102, 101],
  );
  assert.deepEqual(
    run("fases", { competition: "2", season: "20" }).map((item) => item.id),
    [201],
  );
  assert.deepEqual(run("fases", { competition: "2", season: "10" }), []);
  assert.deepEqual(
    data.fases.map((item) => item.id),
    [101, 102, 201],
  );
});

test("search includes accent-insensitive parent names without losing active-state filtering", () => {
  assert.deepEqual(
    run("temporadas", { search: "BOGOTA", active: "true" }).map(
      (item) => item.id,
    ),
    [10],
  );
  assert.equal(
    run("temporadas", { competition: "1", active: "false" }).length,
    0,
  );
});

test("venue and player filters combine their relevant dimensions", () => {
  const venues = [
    { id: 1, nombre: "Estadio Norte", pais: "Colombia", ciudad: "Bogotá" },
    { id: 2, nombre: "Estadio Sur", pais: "Colombia", ciudad: "Cali" },
  ];
  assert.deepEqual(
    run(
      "estadios",
      { country: "Colombia", city: "Bogotá", search: "NORTE" },
      venues,
    ).map((item) => item.id),
    [1],
  );
  const players = [
    {
      id: 1,
      nombre: "Lucho",
      nombre_completo: "Luis Díaz",
      nacionalidad: "Colombia",
      posicion: "Extremo",
    },
    { id: 2, nombre: "Luis", nacionalidad: "Uruguay", posicion: "Delantero" },
  ];
  assert.deepEqual(
    run(
      "jugadores",
      { search: "DIAZ", country: "Colombia", position: "Extremo" },
      players,
    ).map((item) => item.id),
    [1],
  );
});

test("season payload preserves inactive state and validates chronology", () => {
  assert.deepEqual(
    contextPayload("temporadas", {
      nombre: " 2026 ",
      competicion_id: "1",
      fecha_inicio: "",
      fecha_fin: "",
      activa: false,
    }),
    {
      nombre: "2026",
      competicion_id: 1,
      fecha_inicio: null,
      fecha_fin: null,
      activa: false,
    },
  );
  assert.throws(
    () =>
      contextPayload("temporadas", {
        nombre: "2026",
        competicion_id: "1",
        fecha_inicio: "2026-10-01",
        fecha_fin: "2026-01-01",
      }),
    /posterior/,
  );
});

test("phase and venue payloads validate order, coordinates and required identity", () => {
  assert.throws(
    () =>
      contextPayload("fases", {
        nombre: "Final",
        temporada_id: "10",
        orden: "1.5",
      }),
    /entero/,
  );
  assert.throws(
    () =>
      contextPayload("fases", {
        nombre: "Final",
        temporada_id: "",
        orden: "1",
      }),
    /temporada/,
  );
  assert.throws(
    () => contextPayload("estadios", { nombre: "Estadio", latitud: "91" }),
    /latitud/,
  );
  assert.throws(() => contextPayload("estadios", { nombre: "  " }), /nombre/);
  assert.deepEqual(
    contextPayload("estadios", {
      nombre: " Estadio ",
      ciudad: " Bogotá ",
      pais: "Colombia",
      latitud: "0",
      longitud: "",
    }),
    {
      nombre: "Estadio",
      ciudad: "Bogotá",
      pais: "Colombia",
      latitud: 0,
      longitud: null,
    },
  );
});
