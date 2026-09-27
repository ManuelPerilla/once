import { test, expect } from "@playwright/test";

test("context modules isolate their lists, reset dependent filters and save reviewed forms", async ({
  page,
}) => {
  const lists = {
    partidos: [],
    confederaciones: [],
    equipos: [],
    competiciones: [
      {
        id: 1,
        nombre: "Liga Andina",
        tipo: "liga_nacional",
        pais: "Colombia",
        logo: "",
      },
      {
        id: 2,
        nombre: "Copa Pacífico",
        tipo: "copa_nacional",
        pais: "Colombia",
        logo: "",
      },
    ],
    temporadas: [
      { id: 10, competicion_id: 1, nombre: "2026", activa: true },
      { id: 20, competicion_id: 2, nombre: "2026", activa: false },
    ],
    fases: [
      {
        id: 101,
        temporada_id: 10,
        nombre: "Jornada Andina",
        tipo: "jornada",
        orden: 1,
      },
      {
        id: 201,
        temporada_id: 20,
        nombre: "Final Pacífico",
        tipo: "final",
        orden: 1,
      },
    ],
    estadios: [
      {
        id: 30,
        nombre: "Estadio de Bogotá",
        pais: "Colombia",
        ciudad: "Bogotá",
      },
    ],
    jugadores: [
      {
        id: 40,
        nombre: "Jugador de prueba",
        nacionalidad: "Colombia",
        posicion: "Delantero",
      },
    ],
  };
  const writes = [];
  let playerReads = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session"))
      return route.fulfill({
        json: {
          username: "reviewer",
          permissions: [
            "read",
            "correct",
            "operate",
            "manage_sources",
            "manage_accounts",
          ],
        },
      });
    if (path.endsWith("/admin/summary"))
      return route.fulfill({
        json: { counts: { competitions: 2, teams: 0, matches: 0 }, recent: [] },
      });
    const key = path.split("/")[2];
    if (!Object.hasOwn(lists, key)) return route.fulfill({ json: [] });
    if (key === "jugadores" && route.request().method() === "GET")
      playerReads += 1;
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      const record = { id: 999, ...body };
      writes.push({ key, body });
      lists[key].push(record);
      return route.fulfill({ json: record });
    }
    return route.fulfill({ json: lists[key] });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  expect(playerReads).toBe(0);
  await page.getByRole("tab", { name: /^Fases/ }).click();
  const panel = page.getByRole("region", { name: "Fases", exact: true });
  await panel.getByLabel("Competición", { exact: true }).selectOption("1");
  await panel.getByLabel("Temporada", { exact: true }).selectOption("10");
  await expect(
    panel.getByRole("heading", { name: "Jornada Andina" }),
  ).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: "Final Pacífico" }),
  ).toHaveCount(0);
  await panel.getByLabel("Competición", { exact: true }).selectOption("2");
  await expect(panel.getByLabel("Temporada", { exact: true })).toHaveValue("");
  await expect(
    panel
      .getByLabel("Temporada", { exact: true })
      .getByRole("option", { name: "2026", exact: true }),
  ).toHaveAttribute("value", "20");
  await expect(
    panel.getByRole("heading", { name: "Final Pacífico" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Nueva fase" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nombre", { exact: true }).fill("Semifinal revisada");
  await dialog.getByLabel("Temporada", { exact: true }).selectOption("20");
  expect(writes).toHaveLength(0);
  await dialog.getByRole("button", { name: "Guardar ficha" }).click();
  await expect(dialog).toHaveCount(0);
  expect(writes).toEqual([
    {
      key: "fases",
      body: {
        nombre: "Semifinal revisada",
        temporada_id: 20,
        tipo: "jornada",
        orden: 0,
      },
    },
  ]);
  await expect(
    panel.getByRole("heading", { name: "Semifinal revisada" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: /^Estadios/ }).click();
  await expect(
    page.getByRole("region", { name: "Fases", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Estadio de Bogotá" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: /^Jugadores/ }).click();
  await expect(
    page.getByRole("heading", { name: "Jugador de prueba" }),
  ).toBeVisible();
  // Development StrictMode remounts effects once; the first request is cancelled.
  expect(playerReads).toBeGreaterThanOrEqual(1);
  expect(playerReads).toBeLessThanOrEqual(2);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.getByRole("button", { name: "Nuevo jugador" }).click();
  await expect(dialog).toBeVisible();
  expect(
    await dialog
      .getByLabel("Nombre", { exact: true })
      .evaluate((element) =>
        Number.parseFloat(getComputedStyle(element).fontSize),
      ),
  ).toBeGreaterThanOrEqual(16);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect(writes).toHaveLength(1);
});
