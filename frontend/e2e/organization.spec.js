import { test, expect } from "@playwright/test";

test("data control queries real QA records without writes and keeps filters, pagination and mobile views usable", async ({
  page,
  baseURL,
}, testInfo) => {
  const origin = new URL(baseURL);
  // This scenario creates fixtures: never permit an accidental production target.
  expect(["127.0.0.1", "localhost"]).toContain(origin.hostname);
  expect(origin.port).toBe("18080");
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === origin.origin
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/");
  await page
    .getByLabel("Usuario", { exact: true })
    .fill(process.env.SMOKE_USERNAME || "once_test");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar a ONCE" }).click();
  await expect(
    page.getByRole("heading", { name: "Tu centro de operaciones" }),
  ).toBeVisible();

  const suffix = Date.now();
  const provider = `ensayo-organizacion-${suffix}`;
  const prefix = `QA organización ${suffix}`;
  const create = async (path, data) => {
    const response = await page.request.post(`/api/${path}/`, { data });
    expect(response.status(), `Creating disposable ${path}`).toBe(200);
    return response.json();
  };
  for (let index = 1; index <= 21; index += 1) {
    const number = String(index).padStart(2, "0");
    const venue = await create("estadios", {
      nombre: `${prefix} · Estadio ${number}`,
      ciudad: "Bogotá",
      pais: "Colombia",
    });
    await create("providers/mappings", {
      provider,
      entity_type: "venue",
      local_id: venue.id,
      external_id: `recinto-${number}`,
    });
  }
  const player = await create("jugadores", {
    nombre: `${prefix} · Jugador`,
    nacionalidad: "Colombia",
  });
  await create("providers/mappings", {
    provider,
    entity_type: "player",
    local_id: player.id,
    external_id: "jugador-01",
  });
  await create("equipos", {
    nombre: `${prefix} · Afiliación pendiente`,
    logo: "",
    tipo: "club",
    pais: "Colombia",
  });

  // APIRequestContext fixture writes above are deliberate. No browser action below may write.
  const writes = [];
  const pageErrors = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method()))
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  await expect(
    page.getByRole("tab", { name: "Automatización", exact: true }).first(),
  ).toHaveAttribute("aria-selected", "true");
  await page
    .getByRole("tab", { name: "Control de datos", exact: true })
    .click();
  const control = page.getByRole("region", {
    name: "Control de datos",
    exact: true,
  });
  await expect(
    control.getByRole("tab", { name: "Por revisar", exact: true }),
  ).toBeVisible();
  await expect(
    control.getByText(
      "Esta consulta no modifica datos ni contacta con fuentes externas.",
      { exact: false },
    ),
  ).toBeVisible();
  await control.getByRole("tab", { name: "Conexiones", exact: true }).click();
  await control
    .getByLabel("Fuente de los datos", { exact: true })
    .selectOption(provider);
  await expect(control.getByRole("status")).toHaveText(
    "22 registros · Página 1 de 2",
  );
  await control
    .getByLabel("Tipo de registro", { exact: true })
    .selectOption("venue");
  await expect(control.getByRole("status")).toHaveText(
    "21 registros · Página 1 de 2",
  );
  await expect(control.locator(".once-control-record")).toHaveCount(20);
  await control.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(control.getByRole("status")).toHaveText(
    "21 registros · Página 2 de 2",
  );
  await expect(control.locator(".once-control-record")).toHaveCount(1);
  await expect(
    control.getByRole("button", { name: "Siguiente", exact: true }),
  ).toBeDisabled();
  await control.getByRole("button", { name: "Anterior", exact: true }).click();
  await expect(control.getByRole("status")).toHaveText(
    "21 registros · Página 1 de 2",
  );
  await control
    .getByLabel("Buscar en esta revisión", { exact: true })
    .fill("Estadio 07");
  await expect(control.getByRole("status")).toHaveText(
    "1 registros · Página 1 de 1",
  );
  await expect(
    control.getByRole("heading", {
      name: `${prefix} · Estadio 07`,
      exact: true,
    }),
  ).toBeVisible();
  await control
    .getByLabel("Buscar en esta revisión", { exact: true })
    .fill(`ausente-${suffix}`);
  await expect(
    control.getByRole("heading", {
      name: "Sin registros en esta vista",
      exact: true,
    }),
  ).toBeVisible();
  await expect(control.getByRole("status")).toHaveText(
    "0 registros · Página 1 de 1",
  );
  await control
    .getByRole("button", { name: "Limpiar filtros de revisión", exact: true })
    .click();
  await expect(control.getByRole("status")).toContainText(
    "registros · Página 1 de",
  );
  // Same tab and already-empty filters must trigger a usable result, never infinite loading.
  await control
    .getByRole("button", { name: "Limpiar filtros de revisión", exact: true })
    .click();
  await expect(control.getByRole("status")).toContainText(
    "registros · Página 1 de",
  );
  await control.getByRole("tab", { name: "Conexiones", exact: true }).click();
  await expect(control.getByRole("status")).toContainText(
    "registros · Página 1 de",
  );
  await control
    .getByLabel("Fuente de los datos", { exact: true })
    .selectOption(provider);
  await control
    .getByLabel("Tipo de registro", { exact: true })
    .selectOption("player");
  await expect(control.getByRole("status")).toHaveText(
    "1 registros · Página 1 de 1",
  );
  await expect(
    control.getByRole("heading", { name: player.nombre, exact: true }),
  ).toBeVisible();
  for (const title of [
    "Importaciones",
    "Datos consultados",
    "Imágenes y licencias",
  ]) {
    await control.getByRole("tab", { name: title, exact: true }).click();
    await expect(control.getByRole("status")).toContainText(
      "registros · Página 1 de",
    );
    await expect(
      control.getByLabel("Fuente de los datos", { exact: true }),
    ).toHaveValue("");
  }
  await control.getByRole("tab", { name: "Por revisar", exact: true }).click();
  await control
    .getByRole("button", { name: /Equipos sin confederación/ })
    .click();
  await expect(
    control.getByRole("heading", {
      name: "Equipos sin confederación",
      exact: true,
    }),
  ).toBeVisible();
  await expect(control.getByRole("status")).toContainText(
    "registros · Página 1 de",
  );
  await expect(
    control
      .getByText("Revisa si la afiliación está pendiente o no corresponde.", {
        exact: true,
      })
      .first(),
  ).toBeVisible();
  await expect(
    control.getByRole("button", { name: "Ir a equipos →", exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 320, height: 740 });
  await expect(control).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("control-320.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("tab", { name: "Traer información", exact: true })
    .click();
  await expect(control).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("datos-320.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("tab", { name: "Control de datos", exact: true })
    .click();
  await expect(
    control.getByRole("tab", { name: "Por revisar", exact: true }),
  ).toBeVisible();
  expect(writes).toEqual([]);
  expect(pageErrors).toEqual([]);
});
