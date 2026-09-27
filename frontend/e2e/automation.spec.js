import { test, expect } from "@playwright/test";

async function login(
  page,
  username = process.env.SMOKE_USERNAME || "once_test",
  password = process.env.SMOKE_PASSWORD,
) {
  await page.goto("/");
  await page.getByLabel("Usuario", { exact: true }).fill(username);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Entrar a ONCE" }).click();
  await expect(
    page.getByRole("heading", { name: "Tu centro de operaciones" }),
  ).toBeVisible();
}
async function automation(page) {
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  return page.getByRole("region", {
    name: "Automatización de datos",
    exact: true,
  });
}

test("automation preserves pause, protected corrections and responsive controls using the real local API", async ({
  page,
  baseURL,
}) => {
  expect(new URL(baseURL).port).toBe("18080");
  const errors = [];
  const reads = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.method() === "GET") reads.push(new URL(request.url()).pathname);
  });
  await login(page);
  expect(reads).not.toContain("/api/partidos/");
  expect(reads).not.toContain("/api/jugadores/");
  await page.request.put("/api/automation/global", {
    data: { mode: "paused" },
  });
  const area = await automation(page);
  await expect(
    area.getByLabel("Estado general de la automatización"),
  ).toHaveValue("paused");
  await area
    .getByRole("button", { name: "Añadir automatización", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Añadir una automatización",
  });
  const name = `Catálogo QA ${Date.now()}`;
  await dialog.getByLabel("Nombre para reconocer esta tarea").fill(name);
  await dialog.getByRole("button", { name: "Guardar automatización" }).click();
  await expect(dialog).toHaveCount(0);
  const card = area
    .locator(".once-automation-scopes article")
    .filter({ hasText: name });
  await expect(
    card.getByRole("button", { name: "Comprobar ahora" }),
  ).toBeDisabled();
  await area
    .getByLabel("Estado general de la automatización")
    .selectOption("observe");
  await expect(area.locator(".once-automation-success")).toContainText(
    "Control general actualizado",
  );
  await expect(
    card.getByRole("button", { name: "Comprobar ahora" }),
  ).toBeDisabled();
  await area
    .getByLabel("Estado general de la automatización")
    .selectOption("paused");
  await expect(area.locator(".once-automation-success")).toContainText(
    "Pausa solicitada",
  );
  await page.reload();
  await automation(page);
  await expect(
    area.getByLabel("Estado general de la automatización"),
  ).toHaveValue("paused");

  const teamName = `Auditoría QA ${Date.now()}`;
  const created = await page.request.post("/api/equipos/", {
    data: { nombre: teamName, pais: "Colombia", tipo: "club", logo: "" },
  });
  expect(created.ok()).toBeTruthy();
  const team = await created.json();
  await area.getByRole("tab", { name: "Correcciones protegidas" }).click();
  await area
    .getByLabel("Buscar: Ficha que quieres revisar", { exact: true })
    .fill(teamName);
  await area
    .getByLabel("Ficha que quieres revisar", { exact: true })
    .selectOption(String(team.id));
  await area
    .locator(".once-correction-field")
    .filter({ has: page.locator("span", { hasText: /^Nombre$/ }) })
    .click();
  await area
    .getByLabel("Nuevo valor: Nombre", { exact: true })
    .fill(`${teamName} corregido`);
  await area
    .getByLabel("Motivo de la corrección")
    .fill("Nombre contrastado en el archivo oficial de ensayo.");
  await area.getByRole("button", { name: "Guardar y proteger" }).click();
  await expect(area.locator(".once-automation-success")).toContainText(
    "Corrección guardada y protegida",
  );
  const audit = await (
    await page.request.get(`/api/audit/entities/team/${team.id}`)
  ).json();
  expect(audit.fields.find((field) => field.name === "nombre").protected).toBe(
    true,
  );
  expect(audit.history[0].before).toBe(teamName);
  expect(audit.history[0].after).toBe(`${teamName} corregido`);
  await area
    .locator(".once-correction-field")
    .filter({ has: page.locator("span", { hasText: /^Nombre$/ }) })
    .click();
  await area
    .getByLabel("Motivo de la corrección")
    .fill("La fuente ha corregido el nombre y puede actualizarlo.");
  await area
    .getByRole("button", { name: "Volver a aceptar la fuente" })
    .click();
  await expect(area.locator(".once-automation-success")).toContainText(
    "La fuente podrá volver",
  );
  const released = await (
    await page.request.get(`/api/audit/entities/team/${team.id}`)
  ).json();
  expect(
    released.fields.find((field) => field.name === "nombre").protected,
  ).toBe(false);
  await area.getByRole("tab", { name: "Historial de cambios" }).click();
  await expect(
    area.getByRole("heading", { name: "Qué cambió y por qué" }),
  ).toBeVisible();
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `Automation at ${width}`,
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("named auditor account can inspect automation but cannot operate it", async ({
  page,
  browser,
  baseURL,
}) => {
  await login(page);
  const area = await automation(page);
  await area.getByRole("tab", { name: "Personas y permisos" }).click();
  await area.getByRole("button", { name: "Añadir persona" }).click();
  const dialog = page.getByRole("dialog", { name: "Añadir una persona" });
  const username = `qa-auditor-${Date.now()}`;
  const password = `QA-only-${Date.now()}-check`;
  await dialog.getByLabel("Nombre visible").fill("Persona auditora de ensayo");
  await dialog.getByLabel("Nombre de usuario").fill(username);
  await dialog.getByLabel("Contraseña inicial").fill(password);
  await dialog.getByRole("button", { name: "Guardar acceso" }).click();
  await expect(dialog).toHaveCount(0);
  const separate = await browser.newContext({ baseURL });
  const viewer = await separate.newPage();
  await login(viewer, username, password);
  const readOnly = await automation(viewer);
  await expect(
    readOnly.getByLabel("Estado general de la automatización"),
  ).toBeDisabled();
  await expect(
    readOnly.getByRole("button", { name: "Añadir automatización" }),
  ).toBeDisabled();
  await expect(
    readOnly.getByRole("tab", { name: "Personas y permisos" }),
  ).toHaveCount(0);
  expect(
    (
      await viewer.request.put("/api/automation/global", {
        data: { mode: "automatic" },
      })
    ).status(),
  ).toBe(403);
  await separate.close();
});

test("public match pages filter the complete archive and load details only when opened", async ({
  page,
  baseURL,
}) => {
  await login(page);
  const prefix = `Paginación QA ${Date.now()}`;
  const competition = await (
    await page.request.post("/api/competiciones/", {
      data: {
        nombre: prefix,
        tipo: "liga_nacional",
        pais: "Colombia",
        logo: "",
      },
    })
  ).json();
  const teams = [];
  for (const suffix of ["Local", "Visitante"])
    teams.push(
      await (
        await page.request.post("/api/equipos/", {
          data: {
            nombre: `${prefix} ${suffix}`,
            tipo: "club",
            pais: "Colombia",
            logo: "",
          },
        })
      ).json(),
    );
  for (const team of teams)
    expect(
      (
        await page.request.post(
          `/api/equipos/${team.id}/matricular/${competition.id}`,
        )
      ).ok(),
    ).toBeTruthy();
  for (let i = 0; i < 26; i++)
    expect(
      (
        await page.request.post("/api/partidos/", {
          data: {
            competicion_id: competition.id,
            equipo_local_id: teams[0].id,
            equipo_visitante_id: teams[1].id,
            fecha: `2026-10-${String(i + 1).padStart(2, "0")}T20:00:00Z`,
            estado: i === 25 ? "aplazado" : "programado",
            marcador_local: null,
            marcador_visitante: null,
          },
        })
      ).ok(),
    ).toBeTruthy();
  const paths = [];
  page.on("request", (request) => paths.push(new URL(request.url()).pathname));
  await page.goto(`${baseURL}/explore/partidos`);
  await page
    .getByLabel("Filtrar por competición", { exact: true })
    .selectOption(String(competition.id));
  await expect(page.locator(".once-fixture")).toHaveCount(24);
  const next = page.getByRole("button", { name: "Siguiente", exact: true });
  await next.click();
  await expect(page.locator(".once-fixture")).toHaveCount(2);
  expect(paths).not.toContain("/api/public/partidos/");
  expect(paths).not.toContain("/api/public/jugadores/");
  expect(
    paths.some((path) => /^\/api\/public\/partidos\/\d+$/.test(path)),
  ).toBe(false);
  await page.locator(".once-fixture").first().click();
  await expect(page.locator(".p-match-hero")).toBeVisible();
  expect(
    paths.some((path) => /^\/api\/public\/partidos\/\d+$/.test(path)),
  ).toBe(true);
  await expect(page.locator(".p-score-center")).not.toContainText("null");
  await page.getByRole("button", { name: "Equipos", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "Buscar equipo", exact: true })
    .fill(prefix);
  await expect(page.locator(".once-entity-card")).toHaveCount(2);
  await page
    .getByLabel("Filtrar por país", { exact: true })
    .selectOption("Colombia");
  await expect(page.locator(".once-entity-card")).toHaveCount(2);
});
