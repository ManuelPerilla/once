import { expect, test } from "@playwright/test";

async function login(page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
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
}

test("sidebar menu and caption stay separated while scrolling, including short screens", async ({
  page,
}) => {
  await login(page);
  for (const height of [900, 450, 320]) {
    await page.setViewportSize({ width: 1440, height });
    for (const top of [0, 350, 800, 1600]) {
      await page.evaluate((y) => window.scrollTo(0, y), top);
      const menu = await page.locator(".v-nav").boundingBox();
      const caption = await page.locator(".v-nav-caption").boundingBox();
      expect(
        caption.y,
        `Caption below menu at height=${height}, scroll=${top}`,
      ).toBeGreaterThanOrEqual(menu.y + menu.height);
    }
    await page.getByRole("button", { name: "Partidos", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Partidos", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Inicio", exact: true }).click();
  }
});

test("mobile navigation stays usable with large controls and unobscured content", async ({
  page,
}) => {
  await login(page);
  const nav = page.getByRole("navigation", { name: "Navegación principal" });
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await expect(nav).toBeInViewport();
    for (const button of await nav.getByRole("button").all()) {
      await expect(button.locator("svg")).toBeVisible();
      const box = await button.boundingBox();
      expect(box.width).toBeGreaterThanOrEqual(44);
      expect(box.height).toBeGreaterThanOrEqual(44);
    }
    const footer = await page.locator(".v-footer").boundingBox();
    const dock = await page.locator(".v-navigation").boundingBox();
    expect(footer.y + footer.height).toBeLessThanOrEqual(dock.y);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await nav.getByRole("button", { name: "Catálogo", exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await expect(
      page.getByRole("heading", { name: "Catálogo", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Añadir registro", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    const input = dialog.getByLabel("Nombre", { exact: true });
    expect(
      await input.evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
    ).toBeGreaterThanOrEqual(16);
    expect(
      await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.getByRole("button", { name: "Cerrar formulario" }).click();
    await nav.getByRole("button", { name: "Inicio", exact: true }).click();
  }
});
