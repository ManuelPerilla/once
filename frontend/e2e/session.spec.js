import { test, expect } from "@playwright/test";

test("a delayed refresh cannot restore a logged-out session", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Usuario", { exact: true }).fill(process.env.SMOKE_USERNAME || "smoke");
  await page.getByLabel("Contraseña", { exact: true }).fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar al workspace" }).click();
  await expect(page.getByRole("heading", { name: "Tu centro de operaciones" })).toBeVisible();

  let release;
  const held = new Promise(resolve => { release = resolve; });
  let received;
  const arrived = new Promise(resolve => { received = resolve; });
  await page.route("**/api/partidos/", async route => {
    const response = await route.fetch();
    received();
    await held;
    // Cancellation after logout is expected; the held response must not reopen the UI.
    await route.fulfill({ response }).catch(() => {});
  });
  await page.getByRole("button", { name: "Actualizar datos", exact: true }).click();
  await arrived;
  await page.getByRole("button", { name: "Salir de la sesión" }).click();
  await expect(page.getByLabel("Usuario", { exact: true })).toBeVisible();
  release();
  await expect.poll(async () => (await page.request.get("/api/partidos/")).status()).toBe(401);
  await expect(page.getByRole("heading", { name: "Tu centro de operaciones" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Usuario", { exact: true })).toBeVisible();
});
