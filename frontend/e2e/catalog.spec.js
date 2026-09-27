import { test, expect } from "@playwright/test";

async function login(page) {
  await page.goto("/");
  await page
    .getByLabel("Usuario", { exact: true })
    .fill(process.env.SMOKE_USERNAME || "smoke");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar a ONCE" }).click();
  await expect(
    page.getByRole("heading", { name: "Tu centro de operaciones" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  await page
    .getByRole("tab", { name: "Traer información", exact: true })
    .click();
}

test("catalog explains decisions and waits for an explicit save", async ({
  page,
}) => {
  let savedDecisions = null;
  await page.route("**/api/catalog/collections", (route) =>
    route.fulfill({
      json: [
        {
          id: "colombia",
          name: "Fútbol colombiano",
          count: 2,
          description: "Equipos de Colombia.",
        },
      ],
    }),
  );
  await page.route("**/api/catalog/prepare/colombia", (route) =>
    route.fulfill({
      json: {
        id: 9001,
        fetched_at: "2026-09-27T12:00:00Z",
        cached: false,
        rows: [
          {
            qid: "Q332532",
            entity_type: "team",
            nombre: "Deportes Tolima",
            pais: "Colombia",
            status: "review",
            source_url: "https://www.wikidata.org/wiki/Q332532",
            errors: [],
            candidates: [{ id: 41 }],
            choices: [{ id: 41, nombre: "Tolima en ONCE" }],
          },
          {
            qid: "Q2222",
            entity_type: "team",
            nombre: "Equipo nuevo",
            pais: "Colombia",
            status: "new",
            source_url: "https://www.wikidata.org/wiki/Q2222",
            errors: [],
            candidates: [],
            choices: [],
          },
        ],
      },
    }),
  );
  await page.route("**/api/catalog/batches/9001/apply", async (route) => {
    savedDecisions = route.request().postDataJSON().decisions;
    await route.fulfill({ json: { created: 1, linked: 1, reused: 0 } });
  });
  await login(page);
  const importer = page.getByRole("region", {
    name: "Añadir equipos y torneos",
  });
  await importer.getByRole("button", { name: "Buscar y revisar" }).click();
  await expect(
    importer.getByRole("button", { name: "Guardar selección (1)" }),
  ).toBeDisabled();
  expect(savedDecisions).toBeNull();
  await importer
    .getByLabel("Acción para Deportes Tolima")
    .selectOption("link:41");
  await page.getByRole("button", { name: /Buscar escudos e imágenes/ }).click();
  await page.getByRole("button", { name: /Añadir equipos y torneos/ }).click();
  await expect(importer.getByLabel("Acción para Deportes Tolima")).toHaveValue(
    "link:41",
  );
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  await importer.getByRole("button", { name: "Guardar selección (2)" }).click();
  await expect(importer.getByRole("status")).toContainText(
    "añadimos 1 registros, conectamos 1",
  );
  expect(savedDecisions).toEqual([
    { qid: "Q332532", expected_status: "review", action: "link", local_id: 41 },
    { qid: "Q2222", expected_status: "new", action: "create", local_id: null },
  ]);
});

test("crests use named records, show the source and require confirmation", async ({
  page,
}) => {
  let importedUrl = null;
  let previewReads = 0;
  await page.route("**/api/providers/api-football/status", (route) =>
    route.fulfill({ json: { configured: false } }),
  );
  await page.route("**/api/public/equipos/page?*", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 41,
            nombre: "Club de prueba",
            pais: "Colombia",
            tipo: "club",
            competiciones: [],
          },
        ],
        total: 1,
        page: 1,
        page_size: 30,
      },
    }),
  );
  await page.route("**/api/providers/mappings/", (route) =>
    route.fulfill({
      json: [
        {
          provider: "wikidata",
          entity_type: "team",
          local_id: 41,
          external_id: "Q615",
        },
      ],
    }),
  );
  await page.route(
    "**/api/providers/wikidata/preview/Q615/media?purpose=crest",
    async (route) => {
      previewReads += 1;
      await route.fulfill({
        json: {
          filename: "Club crest.svg",
          entity_name: "Club de prueba",
          can_use_as_logo: true,
          thumbnail_url:
            "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cpath fill='lime' d='M10 10h80v50L50 90 10 60Z'/%3E%3C/svg%3E",
          original_url: "https://upload.wikimedia.org/club.svg",
          source_url: "https://commons.wikimedia.org/wiki/File:Club_crest.svg",
          author: "Autor de prueba",
          license: "CC BY-SA 4.0",
        },
      });
    },
  );
  await page.route(
    "**/api/providers/wikidata/import-media/team/41/Q615?**",
    async (route) => {
      importedUrl = new URL(route.request().url());
      await route.fulfill({ json: { id: 1 } });
    },
  );
  await login(page);
  const desk = page.getByRole("region", { name: "Menos trabajo manual." });
  await desk.getByRole("button", { name: /Consultar partidos/ }).click();
  await expect(
    desk.getByRole("button", { name: "Consultar sin guardar" }),
  ).toBeDisabled();
  await expect(desk.getByRole("status")).toContainText(
    "Pide a quien administra la instalación",
  );
  await desk.getByRole("button", { name: /Buscar escudos e imágenes/ }).click();
  await desk
    .getByRole("combobox", { name: "Nombre en tu catálogo", exact: true })
    .selectOption("41");
  await expect(desk.getByLabel("Ficha de Wikidata")).toHaveValue("Q615");
  await desk
    .getByRole("button", { name: "Buscar imagen para revisar" })
    .click();
  await expect(
    desk.getByRole("img", { name: "Imagen encontrada de Club de prueba" }),
  ).toBeVisible();
  await expect(desk.getByText("CC BY-SA 4.0", { exact: true })).toBeVisible();
  expect(importedUrl).toBeNull();
  expect(previewReads).toBe(1);
  await desk.getByLabel("Ficha de Wikidata").fill("Q999");
  await expect(
    desk.getByRole("button", { name: "Guardar esta imagen" }),
  ).toHaveCount(0);
  await desk
    .getByLabel("Ficha de Wikidata")
    .fill("https://www.wikidata.org/wiki/Q615");
  await desk
    .getByRole("button", { name: "Buscar imagen para revisar" })
    .click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await desk.getByRole("button", { name: "Guardar esta imagen" }).click();
  await expect(desk.getByRole("status")).toContainText(
    "Escudo guardado con su fuente y licencia",
  );
  expect(importedUrl.searchParams.get("use_as_logo")).toBe("true");
  expect(importedUrl.searchParams.get("preview_filename")).toBe(
    "Club crest.svg",
  );
});

// External-source integration is opt-in; domain/failure cases run offline in pytest.
test("open catalog imports real Wikidata identities without duplicate teams", async ({
  page,
}) => {
  test.skip(
    process.env.CATALOG_LIVE_TEST !== "1",
    "Requires explicit live-source integration run",
  );
  await page.goto("/");
  await page
    .getByLabel("Usuario", { exact: true })
    .fill(process.env.SMOKE_USERNAME || "smoke");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar a ONCE" }).click();
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  await page
    .getByRole("tab", { name: "Traer información", exact: true })
    .click();
  const importer = page.getByRole("region", {
    name: "Añadir equipos y torneos",
  });
  await expect(importer).toBeVisible();
  await importer.getByLabel("¿Qué quieres añadir?").selectOption("colombia");
  const prepared = page.waitForResponse((response) =>
    response.url().endsWith("/catalog/prepare/colombia"),
  );
  await importer.getByRole("button", { name: "Buscar y revisar" }).click();
  const preparedResponse = await prepared;
  const plan = await preparedResponse.json();
  expect(preparedResponse.status(), JSON.stringify(plan)).toBe(200);
  expect(plan.rows).toHaveLength(21);
  expect(plan.rows.filter((row) => row.status === "blocked")).toHaveLength(0);
  for (const row of plan.rows.filter((item) => item.status === "review")) {
    // The disposable database's seed has these identities under their existing names.
    const known = {
      Q58733: "CONMEBOL",
      Q1033349: "Liga BetPlay",
      Q332532: "Deportes Tolima",
    };
    const candidate = row.choices.find(
      (choice) => choice.nombre === known[row.qid],
    );
    expect(candidate, `Review ${row.nombre}`).toBeTruthy();
    await importer
      .getByLabel(`Acción para ${row.nombre}`)
      .selectOption(`link:${candidate.id}`);
  }
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  await importer
    .getByRole("button", { name: /^Guardar selección \(\d+\)$/ })
    .click();
  await expect(importer.getByRole("status")).toContainText("Listo: añadimos");
  const teams = await (await page.request.get("/api/equipos/")).json();
  expect(
    teams.filter((team) => team.nombre === "Deportes Tolima"),
  ).toHaveLength(1);
  const importedTeam = teams.find(
    (team) => team.nombre === "Atlético Nacional",
  );
  expect(importedTeam).toBeTruthy();
  expect(importedTeam.competiciones).toEqual([]);
  await page.getByRole("button", { name: "Inicio", exact: true }).click();
  await expect(
    page
      .locator(".v-metric")
      .filter({ hasText: "Clubes y selecciones" })
      .locator("strong"),
  ).toHaveText(String(teams.length));
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  await page
    .getByRole("tab", { name: "Traer información", exact: true })
    .click();
  const repeated = page.waitForResponse((response) =>
    response.url().endsWith("/catalog/prepare/colombia"),
  );
  await importer.getByRole("button", { name: "Buscar y revisar" }).click();
  const cached = await (await repeated).json();
  expect(cached.cached).toBe(true);
  expect(cached.id).toBe(plan.id);
  expect(cached.rows.every((row) => row.status === "linked")).toBe(true);
  await expect(
    importer.getByRole("button", { name: "Guardar selección (0)" }),
  ).toBeDisabled();
  const publicTeams = await (
    await page.request.get("/api/public/equipos/")
  ).json();
  expect(publicTeams.some((team) => team.id === importedTeam.id)).toBe(true);
});
