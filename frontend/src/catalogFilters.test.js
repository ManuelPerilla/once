import assert from "node:assert/strict";
import { test } from "node:test";
import {
  EMPTY_FILTERS,
  changeFilters,
  countryOptions,
  filterCatalog,
} from "./catalogFilters.js";

const competitions = [
  {
    id: 1,
    nombre: "Liga BetPlay",
    tipo: "liga_nacional",
    pais: "Colombia",
    confederacion_id: 1,
  },
  {
    id: 2,
    nombre: "Champions League",
    tipo: "internacional_clubes",
    pais: "Internacional",
    confederacion_id: 2,
  },
  {
    id: 3,
    nombre: "Copa Mundial",
    tipo: "internacional_selecciones",
    pais: "Internacional",
    confederacion_id: null,
  },
  {
    id: 4,
    nombre: "Copa Colombia",
    tipo: "copa_nacional",
    pais: "Colombia",
    confederacion_id: 1,
  },
];
const teams = [
  {
    id: 1,
    nombre: "Deportes Tolima",
    tipo: "club",
    pais: "Colombia",
    confederacion_id: 1,
    competiciones: [{ id: 1 }],
  },
  {
    id: 2,
    nombre: "Real Madrid",
    tipo: "club",
    pais: "España",
    confederacion_id: 2,
    competiciones: [{ id: 2 }],
  },
  {
    id: 3,
    nombre: "Colombia",
    tipo: "seleccion",
    pais: "Colombia",
    confederacion_id: 1,
    competiciones: [{ id: 3 }],
  },
  {
    id: 4,
    nombre: "Atlético Nacional",
    tipo: "club",
    pais: "Colombia",
    confederacion_id: 1,
    competiciones: [],
  },
  {
    id: 5,
    nombre: "Sin asignar",
    tipo: "club",
    pais: "Perú",
    confederacion_id: null,
  },
];
const run = (filters = {}) =>
  filterCatalog(competitions, teams, { ...EMPTY_FILTERS, ...filters });
const ids = (items) => items.map((item) => item.id);

test("all catalogues are visible and sorted without mutating source data", () => {
  const before = JSON.stringify({ competitions, teams });
  assert.equal(run().competitions.length, 4);
  assert.equal(run().teams.length, 5);
  assert.equal(run().teams[0].nombre, "Atlético Nacional");
  assert.equal(JSON.stringify({ competitions, teams }), before);
});

test("combines confederation, country and club filters", () => {
  const result = run({
    confederation: "1",
    country: "colombia",
    teamType: "club",
  });
  assert.deepEqual(ids(result.teams), [4, 1]);
  assert.deepEqual(ids(result.competitions), [4, 1]);
});

test("selections are separated from clubs", () => {
  assert.deepEqual(ids(run({ teamType: "seleccion" }).teams), [3]);
});

test("search ignores accents, capitalization and outer whitespace", () => {
  assert.deepEqual(ids(run({ search: "  ATLETICO  " }).teams), [4]);
});

test("competition membership is actual enrollment, not geographic eligibility", () => {
  assert.deepEqual(ids(run({ competition: "1" }).teams), [1]);
  assert.deepEqual(ids(run({ competition: "3" }).teams), [3]);
});

test("searching for a team retains the available competition selector", () => {
  const result = run({ search: "Tolima", competition: "1" });
  assert.deepEqual(ids(result.teams), [1]);
  assert.equal(result.competitions.length, 0);
  assert.equal(result.availableCompetitions.length, 4);
  assert.equal(result.selectedCompetition, "1");
});

test("each competition type can be selected independently", () => {
  for (const item of competitions) {
    assert.deepEqual(ids(run({ competitionType: item.tipo }).competitions), [
      item.id,
    ]);
  }
});

test("global competitions without a confederation remain accessible", () => {
  assert.deepEqual(ids(run({ confederation: "unassigned" }).competitions), [3]);
  assert.deepEqual(ids(run({ confederation: "unassigned" }).teams), [5]);
  assert.deepEqual(ids(run({ country: "Internacional" }).competitions), [2, 3]);
});

test("country options follow confederation and normalize duplicate spellings", () => {
  assert.deepEqual(countryOptions(competitions, teams, "1"), ["Colombia"]);
  assert.deepEqual(
    countryOptions(
      [],
      [...teams, { pais: " colombia ", confederacion_id: 1 }],
      "1",
    ),
    ["Colombia"],
  );
  assert.deepEqual(countryOptions(competitions, teams, "2"), [
    "España",
    "Internacional",
  ]);
});

test("dependent filters reset when their parent changes", () => {
  const filters = {
    ...EMPTY_FILTERS,
    country: "Colombia",
    competition: "1",
    search: "Tolima",
  };
  const next = changeFilters(filters, "confederation", "2");
  assert.equal(next.country, "");
  assert.equal(next.competition, "1");
  assert.equal(next.search, "Tolima");
  assert.equal(filters.country, "Colombia");
  assert.equal(changeFilters(filters, "country", "España").competition, "1");
  assert.equal(
    changeFilters(filters, "competitionType", "copa_nacional").competition,
    "1",
  );
});

test("empty results and missing enrollments are safe", () => {
  assert.deepEqual(run({ search: "inexistente" }).teams, []);
  assert.deepEqual(filterCatalog([], [], EMPTY_FILTERS).teams, []);
  assert.deepEqual(ids(run({ competition: "4" }).teams), []);
});

test("a removed competition cannot leave a hidden membership filter", () => {
  const result = run({ competition: "99" });
  assert.equal(result.selectedCompetition, "");
  assert.equal(result.teams.length, 5);
});

test("clearing filters restores the entire catalogue", () => {
  assert.equal(
    run({ country: "Colombia", teamType: "seleccion", search: "xyz" }).teams
      .length,
    0,
  );
  assert.equal(run({ ...EMPTY_FILTERS }).teams.length, teams.length);
});

test("team geography and tournament geography remain independent", () => {
  const result = run({
    competition: "3",
    country: "Colombia",
    confederation: "1",
  });
  assert.deepEqual(ids(result.teams), [3]);
  assert.equal(result.selectedCompetition, "3");
  assert.ok(result.availableCompetitions.some((item) => item.id === 3));
});
