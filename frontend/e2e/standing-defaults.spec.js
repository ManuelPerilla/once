import { expect, test } from "@playwright/test";

test("standings open a stored table and preserve explicit selections across editions", async ({
  page,
}) => {
  const requests = [];
  const competition = {
    id: 101,
    nombre: "Liga",
    pais: "Colombia",
    tipo: "liga_nacional",
    temporadas: [
      { id: 1, nombre: "Apertura", activa: false },
      { id: 2, nombre: "Clausura", activa: true },
    ],
  };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/changes"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: ": ready\n\n",
      });
    let json = [];
    if (url.pathname.endsWith("/competiciones/")) json = [competition];
    if (url.pathname.endsWith("/partidos/page"))
      json = { items: [], total: 0, page: 1, page_size: 24 };
    const seasonId = Number(url.pathname.split("/").at(-2));
    if (url.pathname.endsWith("/context"))
      json =
        seasonId === 2
          ? {
              phases: [{ id: 20, nombre: "Cuadrangular" }],
              groups: [
                { id: 21, fase_id: 20, nombre: "Grupo A" },
                { id: 22, fase_id: 20, nombre: "Grupo B" },
              ],
              available_standings: [
                { phase_id: 20, group_id: 21, sources: ["official"] },
                { phase_id: 20, group_id: 22, sources: ["official"] },
              ],
            }
          : {
              phases: [{ id: 10, nombre: "Regular" }],
              groups: [],
              available_standings: [
                { phase_id: 10, group_id: null, sources: ["calculated"] },
              ],
            };
    if (url.pathname.endsWith("/clasificacion")) {
      const phase = url.searchParams.get("phase_id"),
        group = url.searchParams.get("group_id");
      requests.push({ seasonId, phase, group });
      const source = seasonId === 2 ? "official" : "calculated";
      json = {
        status: seasonId === 2 ? "missing_rules" : "ready",
        [source]: {
          source: seasonId === 2 ? "api-football" : "once",
          updated_at: "2026-09-27T22:00:00Z",
          rows: [
            {
              rank: 1,
              team: {
                id: 1,
                nombre: `${source} ${seasonId}/${phase}/${group}`,
                logo: "",
              },
              played: 1,
              won: 1,
              drawn: 0,
              lost: 0,
              goals_for: 2,
              goals_against: 0,
              points: 3,
            },
          ],
        },
      };
    }
    await route.fulfill({ json });
  });
  await page.goto("/explore/competiciones/101");
  await page
    .getByRole("navigation", { name: "Secciones de la competición" })
    .getByRole("button", { name: "Clasificación", exact: true })
    .click();
  const phase = page.getByRole("combobox", {
    name: "Fase de la tabla",
    exact: true,
  });
  const group = page.getByRole("combobox", {
    name: "Grupo de la tabla",
    exact: true,
  });
  await expect(phase).toHaveValue("20");
  await expect(group).toHaveValue("21");
  await expect(
    page.getByRole("button", { name: "Tabla de la fuente", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("table")).toContainText("official 2/20/21");
  await group.selectOption("22");
  await expect(page.getByRole("table")).toContainText("official 2/20/22");
  await page.getByRole("button", { name: "Cálculo ONCE", exact: true }).click();
  await expect(
    page.getByText("Esta selección todavía no tiene reglamento registrado.", {
      exact: true,
    }),
  ).toBeVisible();
  const edition = page.getByLabel("Temporada de la competición", {
    exact: true,
  });
  await edition.selectOption("1");
  await expect(phase).toHaveValue("10");
  await expect(group).toHaveValue("");
  await expect(page.getByRole("table")).toContainText("calculated 1/10/null");
  await edition.selectOption("2");
  await expect(phase).toHaveValue("20");
  await expect(group).toHaveValue("22");
  await expect(
    page.getByRole("button", { name: "Cálculo ONCE", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByText("Esta selección todavía no tiene reglamento registrado.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(
    requests.every(
      (request) => request.phase === (request.seasonId === 1 ? "10" : "20"),
    ),
  ).toBe(true);
  expect(
    requests
      .filter((request) => request.seasonId === 1)
      .every((request) => request.group === null),
  ).toBe(true);
});
