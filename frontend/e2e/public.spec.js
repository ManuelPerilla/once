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
  await expect(
    page.getByRole("heading", { name: "El partido, minuto a minuto." }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "EQUIPO LOCAL Atlético del Norte",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Atlético del Norte", exact: true }),
  ).toBeVisible();
  const search = page.getByRole("searchbox");
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
  await expect(page.getByRole("heading", { name: "Donde todo se encuentra.", exact: true })).toBeVisible();
  await page.locator(".once-entity-card").filter({ hasText: "Liga del Horizonte" }).click();
  await expect(
    page.getByRole("heading", { name: "Liga del Horizonte", exact: true }),
  ).toBeVisible();
  expect(apiRequests).toEqual([]);
  expect(errors).toEqual([]);
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
