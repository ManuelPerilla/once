import { test, expect } from "@playwright/test";

async function expectArtwork(page, asset) {
  const artwork = page.locator(".v-hero .v-section-art img");
  await expect(artwork).toHaveAttribute("src", `/art/${asset}.webp`);
  await expect
    .poll(() =>
      artwork.evaluate((image) => image.complete && image.naturalWidth > 0),
    )
    .toBe(true);
}

test.beforeEach(async ({ page, baseURL }) => {
  // Remote crests are decorative. All same-origin frontend and API requests are real.
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === new URL(baseURL).origin
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page
    .getByLabel("Usuario", { exact: true })
    .fill(process.env.SMOKE_USERNAME || "smoke");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar al workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Tu centro de operaciones" }),
  ).toBeVisible();
});

test("real login, catalog, team editor, enrollment, match, reload and logout", async ({
  page,
  context,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const cookie = (await context.cookies()).find(
    (item) => item.name === "vertice_token",
  );
  expect(cookie?.httpOnly).toBe(true);
  await expect(page.getByLabel("Usuario", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveCount(0);
  await expectArtwork(page, "stadium");
  await expect(
    page.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();
  const teamsResponse = await page.request.get("/api/equipos/");
  expect(teamsResponse.status()).toBe(200);
  const initialTeams = await teamsResponse.json();
  await expect(
    page
      .locator(".v-metric")
      .filter({ hasText: "Clubes y selecciones" })
      .locator("strong"),
  ).toHaveText(String(initialTeams.length));

  // Create isolated fixture entities in the disposable CI database, then exercise
  // actual UI writes for team creation/editing, enrollment and a new match.
  const suffix = Date.now();
  const create = async (path, data) => {
    const response = await page.request.post(`/api/${path}/`, { data });
    expect(response.status(), `Creating ${path}`).toBe(200);
    return response.json();
  };
  const conf = await create("confederaciones", {
    nombre: `CI conf ${suffix}`,
    logo: "https://example.test/logo.svg",
  });
  const comp = await create("competiciones", {
    nombre: `CI liga ${suffix}`,
    logo: "https://example.test/logo.svg",
    tipo: "liga_nacional",
    pais: "Colombia",
    confederacion_id: conf.id,
  });
  const visitor = await create("equipos", {
    nombre: `CI visita ${suffix}`,
    logo: "https://example.test/logo.svg",
    tipo: "club",
    pais: "Colombia",
    confederacion_id: conf.id,
  });
  const enrolled = await page.request.post(
    `/api/equipos/${visitor.id}/matricular/${comp.id}`,
  );
  expect(enrolled.status()).toBe(200);
  expect((await enrolled.json()).ok).toBe(true);
  await page
    .getByRole("button", { name: "Actualizar datos", exact: true })
    .click();
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  await expectArtwork(page, "catalog");
  await page.getByRole("tab", { name: /^Equipos/ }).click();
  await page.getByRole("button", { name: "Añadir registro" }).click();
  let dialog = page.getByRole("dialog");
  const name = `CI local ${suffix}`;
  const editedName = `${name} editado`;
  await dialog.getByLabel("Nombre", { exact: true }).fill(name);
  await dialog.getByLabel("País", { exact: true }).fill("Colombia");
  await dialog
    .getByLabel("Confederación", { exact: true })
    .selectOption(String(conf.id));
  await dialog
    .getByLabel("URL del escudo")
    .fill("https://example.test/logo.svg");
  await dialog.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(dialog).toHaveCount(0);
  await page
    .getByRole("button", { name: `Editar ${name}`, exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nombre", { exact: true }).fill(editedName);
  await dialog.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(
    page.getByRole("button", { name: `Editar ${editedName}`, exact: true }),
  ).toBeVisible();
  await page.getByLabel("Buscar por nombre").fill(editedName);
  await expect(page.locator(".v-catalog-row")).toHaveCount(1);
  const storedTeams = await (await page.request.get("/api/equipos/")).json();
  const local = storedTeams.find((item) => item.nombre === editedName);
  expect(local?.confederacion_id).toBe(conf.id);
  expect(local?.competiciones).toHaveLength(0);
  await page
    .getByRole("button", { name: `Eliminar ${editedName}`, exact: true })
    .click();
  const confirmation = page.getByRole("dialog");
  await expect(confirmation).toContainText("Sus partidos se conservarán");
  await expect(
    confirmation.getByRole("button", { name: "Cancelar", exact: true }),
  ).toBeFocused();
  await confirmation
    .getByRole("button", { name: "Cancelar", exact: true })
    .click();
  await expect(confirmation).toHaveCount(0);
  expect((await page.request.get("/api/equipos/")).status()).toBe(200);
  await expect(
    page.getByRole("button", { name: `Editar ${editedName}`, exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Matrículas", exact: true }).click();
  await expectArtwork(page, "registration");
  await page.locator("#matricula-competition").selectOption(String(comp.id));
  await expect(
    page
      .getByLabel(/Equipo compatible/)
      .locator(`option[value="${visitor.id}"]`),
  ).toHaveCount(0);
  await page.getByLabel(/Equipo compatible/).selectOption(String(local.id));
  await page.getByRole("button", { name: "Confirmar matrícula" }).click();
  await expect(page.getByLabel(/Equipo compatible/)).toBeDisabled();
  const afterEnrollment = await (
    await page.request.get("/api/equipos/")
  ).json();
  expect(
    afterEnrollment
      .find((item) => item.id === local.id)
      .competiciones.map((item) => item.id),
  ).toContain(comp.id);

  await page.getByRole("button", { name: "Partidos", exact: true }).click();
  await expectArtwork(page, "matchday");
  await page
    .getByRole("button", { name: "Registrar partido", exact: true })
    .first()
    .click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Competición", { exact: true })
    .selectOption(String(comp.id));
  await dialog
    .getByLabel("Equipo local", { exact: true })
    .selectOption(String(local.id));
  await expect(
    dialog
      .getByLabel("Equipo visitante")
      .locator(`option[value="${local.id}"]`),
  ).toHaveCount(0);
  await dialog
    .getByLabel("Equipo visitante", { exact: true })
    .selectOption(String(visitor.id));
  await dialog.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.locator(".v-match-row").filter({ hasText: comp.nombre }),
  ).toBeVisible();
  const matches = await (await page.request.get("/api/partidos/")).json();
  expect(
    matches.some(
      (item) =>
        item.competicion_id === comp.id &&
        item.equipo_local_id === local.id &&
        item.equipo_visitante_id === visitor.id,
    ),
  ).toBe(true);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: "Tu centro de operaciones" }),
  ).toBeVisible();
  await expect(
    page.locator(".v-match-row").filter({ hasText: comp.nombre }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Partidos", exact: true }).click();
  const storedMatch = matches.find(
    (item) =>
      item.competicion_id === comp.id && item.equipo_local_id === local.id,
  );
  await page
    .getByRole("button", {
      name: `Eliminar partido ${storedMatch.id}`,
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "También se eliminarán las estadísticas",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Eliminar registro", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.locator(".v-match-row").filter({ hasText: comp.nombre }),
  ).toHaveCount(0);
  const afterDelete = await (await page.request.get("/api/partidos/")).json();
  expect(afterDelete.some((item) => item.id === storedMatch.id)).toBe(false);
  expect(
    (await (await page.request.get("/api/equipos/")).json()).some(
      (item) => item.id === local.id,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Salir de la sesión", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bienvenido de nuevo." }),
  ).toBeVisible();
  expect((await page.request.get("/api/partidos/")).status()).toBe(401);
  expect(
    (await context.cookies()).some((item) => item.name === "vertice_token"),
  ).toBe(false);
  expect(errors).toEqual([]);
});

test("mobile home, catalogue and modal stay usable with real data", async ({
  page,
}) => {
  const fitsScreen = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await fitsScreen(), `Home fits ${width}px`).toBe(true);
    await expectArtwork(page, "stadium");
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  await page.getByRole("tab", { name: /^Equipos/ }).click();
  await page.getByRole("tab", { name: /^Equipos/ }).press("End");
  await expect(
    page.getByRole("tab", { name: /^Confederaciones/ }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: /^Confederaciones/ }).press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /^Equipos/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(await fitsScreen()).toBe(true);
  await page.getByRole("button", { name: "Añadir registro" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  for (const [section, asset] of [
    ["Matrículas", "registration"],
    ["Partidos", "matchday"],
  ]) {
    await page.getByRole("button", { name: section, exact: true }).click();
    await expectArtwork(page, asset);
    expect(await fitsScreen(), `${section} fits mobile`).toBe(true);
  }
});
