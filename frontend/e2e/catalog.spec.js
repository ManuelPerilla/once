import { test, expect } from "@playwright/test";

// External-source integration is opt-in; domain/failure cases run offline in pytest.
test("open catalog imports real Wikidata identities without duplicate teams", async ({ page }) => {
  test.skip(process.env.CATALOG_LIVE_TEST !== "1", "Requires explicit live-source integration run");
  await page.goto("/");
  await page.getByLabel("Usuario", { exact: true }).fill(process.env.SMOKE_USERNAME || "smoke");
  await page.getByLabel("Contraseña", { exact: true }).fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar al workspace" }).click();
  const importer = page.getByRole("region", { name: "Haz crecer tu catálogo." });
  await expect(importer).toBeVisible();
  await importer.getByLabel("Colección de datos abiertos").selectOption("colombia");
  const prepared = page.waitForResponse((response) => response.url().endsWith("/catalog/prepare/colombia"));
  await importer.getByRole("button", { name: "Preparar vista previa" }).click();
  const preparedResponse = await prepared;
  const plan = await preparedResponse.json();
  expect(preparedResponse.status(), JSON.stringify(plan)).toBe(200);
  expect(plan.rows).toHaveLength(21);
  expect(plan.rows.filter((row) => row.status === "blocked")).toHaveLength(0);
  for (const row of plan.rows.filter((item) => item.status === "review")) {
    // The disposable database's seed has these identities under their existing names.
    const known = { Q58733: "CONMEBOL", Q1033349: "Liga BetPlay", Q332532: "Deportes Tolima" };
    const candidate = row.choices.find((choice) => choice.nombre === known[row.qid]);
    expect(candidate, `Review ${row.nombre}`).toBeTruthy();
    await importer.getByLabel(`Acción para ${row.nombre}`).selectOption(`link:${candidate.id}`);
  }
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await importer.getByRole("button", { name: /^Importar \d+ registros$/ }).click();
  await expect(importer.getByRole("status")).toContainText("Importación completada");
  const teams = await (await page.request.get("/api/equipos/")).json();
  expect(teams.filter((team) => team.nombre === "Deportes Tolima")).toHaveLength(1);
  const importedTeam = teams.find((team) => team.nombre === "Atlético Nacional");
  expect(importedTeam).toBeTruthy();
  expect(importedTeam.competiciones).toEqual([]);
  await expect(page.locator(".v-metric").filter({ hasText: "Clubes y selecciones" }).locator("strong")).toHaveText(String(teams.length));
  const repeated = page.waitForResponse((response) => response.url().endsWith("/catalog/prepare/colombia"));
  await importer.getByRole("button", { name: "Preparar vista previa" }).click();
  const cached = await (await repeated).json();
  expect(cached.cached).toBe(true);
  expect(cached.id).toBe(plan.id);
  expect(cached.rows.every((row) => row.status === "linked")).toBe(true);
  await expect(importer.getByRole("button", { name: "Importar 0 registros" })).toBeDisabled();
  const publicTeams = await (await page.request.get("/api/public/equipos/")).json();
  expect(publicTeams.some((team) => team.id === importedTeam.id)).toBe(true);
});
