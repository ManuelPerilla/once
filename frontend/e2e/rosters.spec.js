import { expect, test } from "@playwright/test";

test("rosters remain a separate read-only module with explicit date semantics", async ({
  page,
}) => {
  const calls = [];
  const rows = [
    {
      id: 1,
      jugador_id: 7,
      equipo_id: 1,
      jugador_nombre: "Ana del Norte",
      equipo_nombre: "Equipo del Norte",
      fecha_inicio: "2025-01-01",
      fecha_fin: null,
      dorsal: 0,
    },
    {
      id: 2,
      jugador_id: 8,
      equipo_id: 2,
      jugador_nombre: "Luis del Sur",
      equipo_nombre: "Equipo del Sur",
      fecha_inicio: null,
      fecha_fin: "2099-12-31",
      dorsal: null,
    },
  ];
  await page.route("**/api/plantillas/?*", (route) => {
    const request = route.request();
    const params = new URL(request.url()).searchParams;
    calls.push({
      method: request.method(),
      state: params.get("estado"),
      search: params.get("search"),
    });
    const state = params.get("estado");
    const search = (params.get("search") || "").toLowerCase();
    const items = rows.filter(
      (row) =>
        (!state ||
          (state === "active" ? !row.fecha_fin : Boolean(row.fecha_fin))) &&
        row.jugador_nombre.toLowerCase().includes(search),
    );
    return route.fulfill({
      json: { items, total: items.length, page: 1, page_size: 20 },
    });
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page
    .getByLabel("Usuario", { exact: true })
    .fill(process.env.SMOKE_USERNAME || "smoke");
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(process.env.SMOKE_PASSWORD);
  await page.getByRole("button", { name: "Entrar a ONCE" }).click();
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  expect(calls).toEqual([]);
  await page.getByRole("tab", { name: "Plantillas", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Pertenencia de jugadores a equipos",
  });
  await expect(panel.getByRole("status")).toContainText("2 vínculos");
  await expect(panel).toContainText("no confirma que el jugador siga hoy");
  await expect(
    page.getByRole("button", { name: "Añadir registro" }),
  ).toHaveCount(0);
  await panel.getByLabel("Estado del vínculo").selectOption("closed");
  await expect(
    panel.getByRole("heading", { name: "Luis del Sur" }),
  ).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: "Ana del Norte" }),
  ).toHaveCount(0);
  await expect(panel).toContainText("31/12/2099");
  await panel.getByLabel("Estado del vínculo").selectOption("active");
  await expect(
    panel.getByRole("heading", { name: "Ana del Norte" }),
  ).toBeVisible();
  await expect(panel.locator("dd", { hasText: /^0$/ })).toBeVisible();
  await panel.getByLabel("Buscar jugador o equipo").fill("ausente");
  await expect(panel.getByText("Sin vínculos en esta vista")).toBeVisible();
  await panel
    .getByRole("button", { name: "Limpiar filtros de plantillas" })
    .click();
  await expect(panel.getByRole("status")).toContainText("2 vínculos");
  await panel
    .getByRole("button", { name: "Limpiar filtros de plantillas" })
    .click();
  await expect(panel.getByRole("status")).toContainText("2 vínculos");
  await page.setViewportSize({ width: 320, height: 740 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(calls.every((call) => call.method === "GET")).toBe(true);
});
