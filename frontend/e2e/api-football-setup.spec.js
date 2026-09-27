import { expect, test } from "@playwright/test";

const connected = {
  configured: true,
  state: "connected",
  checked_at: "2026-09-28T12:00:00Z",
  account: {
    active: true,
    plan: "Free",
    requests_current: 8,
    requests_limit_day: 100,
    allowed_seasons: [2022, 2023, 2024],
    current_access: false,
    access_checked_at: "2026-09-27T22:00:00Z",
  },
  competitions: [
    {
      league_id: 239,
      name: "Primera A",
      country: "Colombia",
      seasons: [
        { year: 2026, current: true },
        { year: 2025 },
        {
          year: 2024,
          coverage: {
            standings: true,
            fixtures: { events: true, lineups: true },
          },
        },
      ],
    },
  ],
  profiles: [],
  global_mode: "paused",
};

async function mockSetup(
  page,
  initial,
  permissions = ["manage_sources", "operate"],
) {
  let connection = structuredClone(initial);
  const writes = [];
  const reads = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api/, "");
    if (request.method() === "GET") reads.push(path);
    else writes.push({ path, body: request.postDataJSON() });
    let json = [];
    if (path === "/auth/session") json = { username: "QA", permissions };
    if (path === "/admin/summary") json = { recent: [], counts: {} };
    if (path === "/automation/providers") json = { items: [] };
    if (path === "/automation/jobs")
      json = {
        total: 2,
        items: [
          {
            id: 701,
            kind: "details_batch",
            status: "succeeded",
            result: { matches_checked: 20, matches_received: 18, more: true },
          },
          {
            id: 702,
            kind: "standings_batch",
            status: "succeeded",
            result: { tables: 4 },
          },
        ],
      };
    if (path === "/automation/overview")
      json = {
        global: { mode: "paused" },
        scopes: [],
        jobs: {},
        worker: { healthy: true },
      };
    if (path === "/providers/api-football/connection") json = connection;
    if (path === "/providers/api-football/check") {
      connection = structuredClone(connected);
      json = connection;
    }
    if (path === "/providers/api-football/prepare") {
      connection.profiles = [
        { id: 61, name: "Primera A · 2024 · Calendario", mode: "paused" },
        { id: 62, name: "Primera A · 2024 · Detalles", mode: "paused" },
      ];
      json = { scope_ids: [61, 62], created: 2, connection };
    }
    if (path.startsWith("/automation/scopes/")) {
      const profile = connection.profiles.find((item) =>
        path.endsWith(`/${item.id}`),
      );
      profile.mode = request.postDataJSON().mode;
      json = profile;
    }
    await route.fulfill({ json });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  const panel = page.getByRole("region", { name: "Conecta el juego real." });
  await expect(panel).toBeVisible();
  return { panel, writes, reads };
}

test("missing API key is explained without collecting secrets or calling the provider", async ({
  page,
}) => {
  const { panel, writes } = await mockSetup(page, {
    configured: false,
    state: "missing_key",
  });
  await expect(
    panel.getByText("Pendiente de conectar", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Comprobar cuenta y cobertura" }),
  ).toBeDisabled();
  await expect(panel.locator("input")).toHaveCount(0);
  await panel
    .getByRole("button", { name: "Volver a leer configuración" })
    .click();
  await expect(panel.getByRole("status")).toContainText("no consume cuota");
  expect(writes).toEqual([]);
});

test("onboarding prepares published years and activates selected tasks while preserving global pause", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const { panel, writes } = await mockSetup(page, {
    configured: true,
    state: "unchecked",
  });
  await expect(panel.getByText(/falta comprobar/)).toBeVisible();
  expect(writes).toEqual([]);
  await panel
    .getByRole("button", { name: "Comprobar cuenta y cobertura" })
    .click();
  await expect(
    panel.getByText("Cuenta comprobada", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("92 de 100 disponibles", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByRole("combobox")).toHaveValue("2024");
  await expect(
    panel.getByText("Tu suscripción está activa.", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText(/El plan actual no permite consultar la temporada vigente/),
  ).toBeVisible();
  await expect(
    panel.getByText(/permite las temporadas 2022, 2023, 2024/),
  ).toBeVisible();
  await expect(panel.getByRole("option", { name: /2026/ })).toHaveCount(0);
  await expect(panel.getByText(/El acceso efectivo a partidos/)).toBeVisible();
  await panel
    .getByRole("checkbox", { name: "Primera A Colombia", exact: true })
    .check();
  await panel
    .getByRole("button", { name: "Preparar 1 competición", exact: true })
    .click();
  await expect(
    panel.getByRole("heading", { name: "Tu selección está preparada" }),
  ).toBeVisible();
  expect(writes.find((item) => item.path.endsWith("/prepare")).body).toEqual({
    selections: [{ league_id: 239, season: 2024 }],
    include_details: true,
  });
  await panel
    .getByRole("button", { name: "Activar estas actualizaciones" })
    .click();
  await expect(
    panel.getByRole("button", { name: "Actualizaciones activadas" }),
  ).toBeDisabled();
  await expect(
    panel.getByText(/El control general está en Pausado/),
  ).toBeVisible();
  expect(writes.filter((item) => item.path === "/automation/global")).toEqual(
    [],
  );
  expect(
    writes.filter((item) => item.path.startsWith("/automation/scopes/")),
  ).toEqual([
    { path: "/automation/scopes/61", body: { mode: "automatic" } },
    { path: "/automation/scopes/62", body: { mode: "automatic" } },
  ]);
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("an auditor can inspect coverage but cannot spend quota or prepare jobs", async ({
  page,
}) => {
  const { panel, writes } = await mockSetup(page, connected, []);
  await expect(
    panel.getByRole("button", { name: "Comprobar cuenta y cobertura" }),
  ).toBeDisabled();
  await expect(
    panel.getByRole("checkbox", { name: "Primera A Colombia", exact: true }),
  ).toBeDisabled();
  await expect(
    panel.getByRole("button", { name: "Preparar las competiciones" }),
  ).toBeDisabled();
  expect(writes).toEqual([]);
});

test("batch activity explains progress using readable football terms", async ({
  page,
}) => {
  await mockSetup(page, connected);
  await page.getByRole("tab", { name: "Actividad", exact: true }).click();
  const activity = page.locator(".once-automation-records");
  await expect(
    activity.getByText("Detalle de los partidos seleccionados", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(activity).toContainText(
    "20 partidos consultados para completar su detalle",
  );
  await expect(activity).toContainText("18 partidos devueltos por la fuente");
  await expect(activity).toContainText("continuará con el siguiente lote");
  await expect(activity).not.toContainText("details_batch");
  await expect(
    activity.getByText("Clasificaciones de la temporada", { exact: true }),
  ).toBeVisible();
  await expect(activity).toContainText("4 clasificaciones incorporadas");
  await expect(activity).not.toContainText("standings_batch");
});
