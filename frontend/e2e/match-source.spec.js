import { expect, test } from "@playwright/test";

test("public matches distinguish manual, provider, historical and unknown sources", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const competition = { id: 10, nombre: "Liga de prueba", temporadas: [] };
  const sources = [
    { provider: "manual", verified_at: null },
    { provider: "api-football", verified_at: "2026-09-27T20:00:00Z" },
    { provider: "openfootball", verified_at: "2026-09-26T20:00:00Z" },
    undefined,
  ];
  const labels = [
    "Registro manual",
    "API-Football",
    "Archivo abierto",
    "Origen sin confirmar",
  ];
  const matches = sources.map((source, index) => ({
    id: index + 1,
    competicion: competition,
    competicion_id: competition.id,
    fecha: "2026-09-26T20:00:00Z",
    equipo_local: { id: 1, nombre: "Local", logo: "" },
    equipo_visitante: { id: 2, nombre: "Visitante", logo: "" },
    marcador_local: 1,
    marcador_visitante: 0,
    estado: index === 0 ? "en vivo" : "finalizado",
    ...(source ? { data_source: source } : {}),
  }));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/changes"))
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: ": heartbeat\n\n",
      });
    let json = [];
    if (path.endsWith("/competiciones/")) json = [competition];
    if (path.endsWith("/partidos/page"))
      json = { items: matches, total: matches.length, page: 1, page_size: 24 };
    if (/\/partidos\/\d+$/.test(path))
      json = matches.find(
        (match) => String(match.id) === path.split("/").at(-1),
      );
    await route.fulfill({ json });
  });
  await page.goto("/explore/partidos");
  const cards = page.locator(".once-fixture");
  await expect(cards).toHaveCount(4);
  for (let index = 0; index < labels.length; index += 1) {
    await expect(cards.nth(index).locator(".once-match-source")).toHaveText(
      labels[index],
    );
  }
  await expect(cards.first()).toContainText("En vivo");
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  for (let index = 0; index < labels.length; index += 1) {
    await page.goto(`/explore/partidos/${index + 1}`);
    const source = page.locator(".p-match-hero > .once-match-source");
    await expect(source).toContainText(labels[index]);
    if (index === 1) await expect(source).toContainText("Fuente comprobada");
    if (index === 3) await expect(source).not.toContainText("API-Football");
  }
  expect(errors).toEqual([]);
});
