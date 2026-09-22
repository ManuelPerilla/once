import { expect, test } from "@playwright/test";

test("public experience opens without an admin session", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/explore");

  await expect(
    page.getByRole("heading", { name: /sigue el hilo/i }),
  ).toBeVisible();
  await expect(page.getByText("FÚTBOL · CONTEXTO · CONEXIONES")).toBeVisible();
  await expect(page.getByRole("link", { name: /administración/i })).toHaveAttribute(
    "href",
    "/",
  );
});

test("public experience does not render the admin login form", async ({ page }) => {
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
  await expect(page.getByRole("heading", { name: /Deportes Tolima/i })).toBeVisible();
});

