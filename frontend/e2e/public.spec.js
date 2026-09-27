import { expect, test } from "@playwright/test";

test("public experience opens without an admin session", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/explore");

  await expect(
    page.getByRole("heading", { name: /el juego. todo conectado./i }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Explorar fútbol" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /administración/i }),
  ).toHaveAttribute("href", "/");
});

test("public experience does not render the admin login form", async ({
  page,
}) => {
  await page.context().clearCookies();
  await page.goto("/explore");

  await expect(page.getByLabel("Usuario")).toHaveCount(0);
  await expect(page.getByLabel("Contraseña")).toHaveCount(0);
});

test("public search follows a team connection", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/explore");

  const search = page.getByRole("searchbox", {
    name: /buscar equipos, competiciones, jugadores o partidos/i,
  });
  await search.fill("Tolima");

  const result = page.getByRole("button", { name: /Deportes Tolima/i }).first();
  await expect(result).toBeVisible();
  await result.click();

  await expect(page).toHaveURL(/\/explore\/equipos\/\d+$/);
  await expect(
    page.getByRole("heading", { name: /Deportes Tolima/i }),
  ).toBeVisible();
});

test("demo filters, connections and keyboard search work without API requests", async ({
  page,
}) => {
  const apiRequests = [];
  const errors = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/"))
      apiRequests.push(request.url());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explore?demo=1");
  await page
    .getByRole("button", { name: "Pausar animación", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Reanudar animación" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Explorar partidos", exact: true })
    .click();
  await page.getByRole("button", { name: "Próximos 2", exact: true }).click();
  await expect(page.locator(".once-fixture")).toHaveCount(2);
  await page
    .getByLabel("Filtrar por competición")
    .selectOption({ label: "Copa Capital" });
  await expect(page.getByText("Aquí todavía no rueda el balón.")).toBeVisible();
  await page.getByRole("button", { name: "Restablecer filtros" }).click();
  await page
    .getByRole("button", { name: /Liga del Horizonte En vivo/ })
    .click();
  await page
    .getByRole("navigation", { name: "Secciones del partido" })
    .getByRole("button", { name: "Cronología 4" })
    .click();
  await expect(
    page.getByRole("heading", { name: "El partido, minuto a minuto." }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Secciones del partido" })
    .getByRole("button", { name: "Conexiones", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "EQUIPO LOCAL Atlético del Norte",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Atlético del Norte", exact: true }),
  ).toBeVisible();
  const search = page.getByRole("searchbox", {
    name: "Buscar equipos, competiciones, jugadores o partidos",
  });
  await search.fill("aurora");
  await search.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Club Aurora", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/explore\/equipos\/5\?demo=1$/);
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Atlético del Norte", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Competiciones", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Donde todo se encuentra.",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .locator(".once-entity-card")
    .filter({ hasText: "Liga del Horizonte" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Liga del Horizonte", exact: true }),
  ).toBeVisible();
  expect(apiRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test("public modules keep match information separate and filters explain their scope", async ({
  page,
}) => {
  await page.goto("/explore/partidos/1?demo=1");
  const sections = page.getByRole("navigation", {
    name: "Secciones del partido",
  });
  await expect(
    page.getByRole("heading", { name: "Lo que sí sabemos." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "El partido, minuto a minuto." }),
  ).toHaveCount(0);
  await sections.getByRole("button", { name: "Cronología 4" }).click();
  await expect(
    page.getByRole("heading", { name: "El partido, minuto a minuto." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Lo que sí sabemos." }),
  ).toHaveCount(0);
  await sections.getByRole("button", { name: "Alineaciones 0" }).click();
  await expect(
    page.getByRole("heading", { name: "Alineación por confirmar" }),
  ).toBeVisible();

  await page
    .getByRole("navigation", { name: "Explorar fútbol" })
    .getByRole("button", { name: "Equipos", exact: true })
    .click();
  await page
    .getByLabel("Filtrar equipos por competición")
    .selectOption({ label: "Copa del Pacífico" });
  await expect(page.locator(".once-entity-card")).toHaveCount(2);
  await page.getByLabel("Filtrar por país").selectOption("Ecuador");
  await expect(page.locator(".once-entity-card")).toHaveCount(1);
  await expect(page.getByRole("status")).toContainText("1 de 6 equipos");
  await page
    .getByRole("button", { name: "Limpiar filtros", exact: true })
    .click();
  await expect(page.locator(".once-entity-card")).toHaveCount(6);
  await page
    .getByRole("searchbox", {
      name: "Buscar equipos, competiciones, jugadores o partidos",
    })
    .fill("colombia");
  await expect(
    page.locator(".once-search-group").filter({ hasText: "Equipos" }),
  ).toBeVisible();
  await expect(
    page.locator(".once-search-group").filter({ hasText: "Competiciones" }),
  ).toBeVisible();
});

test("competition season selection isolates fixtures, phases and standings", async ({
  page,
}) => {
  const competition = {
    id: 101,
    nombre: "Liga de prueba",
    pais: "Colombia",
    tipo: "liga_nacional",
    temporadas: [
      { id: 1, nombre: "2025", activa: false },
      { id: 2, nombre: "2026", activa: true },
    ],
  };
  const teams = [1, 2, 3, 4, 5, 6].map((id) => ({
    id,
    nombre: `Equipo ${id}`,
    tipo: "club",
    pais: "Colombia",
    logo: "",
  }));
  const matches = [1, 2, 3].map((id) => ({
    id,
    estado: "finalizado",
    competicion_id: 101,
    competicion: competition,
    temporada_id: id === 3 ? null : id,
    equipo_local_id: id * 2 - 1,
    equipo_visitante_id: id * 2,
    equipo_local: teams[id * 2 - 2],
    equipo_visitante: teams[id * 2 - 1],
    marcador_local: id,
    marcador_visitante: 0,
    fase: { id, nombre: `Fase ${id}`, orden: 1, tipo: "jornada" },
  }));
  const seasonRequests = [];
  await page.route("**/api/public/**", async (route) => {
    const url = new URL(route.request().url());
    let body = [];
    if (url.pathname.endsWith("/competiciones/")) body = [competition];
    if (url.pathname.endsWith("/equipos/page"))
      body = { items: teams, total: teams.length, page: 1, page_size: 24 };
    if (url.pathname.endsWith("/partidos/page")) {
      const season = url.searchParams.get("season_id");
      const selected = matches.filter(
        (match) =>
          !season ||
          (season === "unassigned"
            ? match.temporada_id === null
            : String(match.temporada_id) === season),
      );
      body = {
        items: selected,
        total: selected.length,
        page: 1,
        page_size: 24,
      };
    }
    if (url.pathname.endsWith("/context")) body = { phases: [], groups: [] };
    if (url.pathname.endsWith("/clasificacion")) {
      const season = url.pathname.split("/").at(-2);
      seasonRequests.push(season);
      body = {
        status: "ready",
        calculated: {
          updated_at: "2026-09-27T00:00:00Z",
          rows: [
            {
              rank: 1,
              team: teams[Number(season) * 2 - 2],
              played: 1,
              won: 1,
              drawn: 0,
              lost: 0,
              goal_difference: 2,
              points: 3,
            },
          ],
        },
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/explore/competiciones/101");
  const sections = page.getByRole("navigation", {
    name: "Secciones de la competición",
  });
  await expect(page.getByLabel("Temporada de la competición")).toHaveValue("2");
  await expect(page.locator(".once-fixture")).toHaveCount(1);
  await expect(page.locator(".once-fixture")).toContainText("Equipo 3");
  await sections.getByRole("button", { name: "Fases", exact: true }).click();
  await expect(page.locator(".p-stage-column")).toHaveCount(1);
  await expect(page.locator(".p-stage-column")).toContainText("Fase 2");
  await sections
    .getByRole("button", { name: "Clasificación", exact: true })
    .click();
  await expect(page.getByRole("table")).toContainText("Equipo 3");
  await page.getByLabel("Temporada de la competición").selectOption("1");
  await expect(page.getByRole("table")).toContainText("Equipo 1");
  await expect(page.getByRole("table")).not.toContainText("Equipo 3");
  expect([...new Set(seasonRequests)]).toEqual(["2", "1"]);
  const requestsBeforeUnassigned = seasonRequests.length;
  await page
    .getByLabel("Temporada de la competición")
    .selectOption("unassigned");
  await expect(
    page.getByRole("heading", {
      name: "Elige una temporada para ver la tabla",
    }),
  ).toBeVisible();
  await sections.getByRole("button", { name: "Partidos", exact: true }).click();
  await expect(page.locator(".once-fixture")).toContainText("Equipo 5");
  expect(seasonRequests).toHaveLength(requestsBeforeUnassigned);
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `Competition at ${width}`,
    ).toBe(true);
  }
});

test("public demo fits mobile, tablet and desktop with reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/explore?demo=1");
  await expect(
    page.getByRole("heading", { name: /el juego. todo conectado./i }),
  ).toBeVisible();
  for (const width of [320, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `Homepage at ${width}`,
    ).toBe(true);
    expect(
      await page
        .locator(".once-hero-copy")
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
      `Hero at ${width}`,
    ).toBe(true);
  }
  await expect(page.locator(".once-pitch-art")).toHaveCSS(
    "animation-name",
    "none",
  );
  await page.setViewportSize({ width: 320, height: 800 });
  await page.getByRole("button", { name: "Equipos", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "Buscar equipo", exact: true })
    .fill("inexistente");
  await expect(
    page.getByRole("heading", { name: "No encontramos coincidencias." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Limpiar filtros" }).click();
  await expect(page.locator(".once-entity-card")).toHaveCount(6);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
