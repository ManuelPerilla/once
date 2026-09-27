import { test, expect } from "@playwright/test";

test("reviewed sporting rules publish a versioned calculation separate from the source table", async ({
  page,
}) => {
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
  const prefix = `Reglamento QA ${Date.now()}`;
  const create = async (path, data) => {
    const response = await page.request.post(`/api/${path}`, { data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const competition = await create("competiciones/", {
    nombre: prefix,
    pais: "Colombia",
    tipo: "liga_nacional",
    logo: "",
  });
  const season = await create("temporadas/", {
    competicion_id: competition.id,
    nombre: `${prefix} 2026`,
    activa: true,
  });
  const teams = [];
  for (const suffix of ["A", "B"]) {
    const team = await create("equipos/", {
      nombre: `${prefix} ${suffix}`,
      pais: "Colombia",
      tipo: "club",
      logo: "",
    });
    await page.request.post(
      `/api/equipos/${team.id}/matricular/${competition.id}`,
    );
    await create(`football/temporadas/${season.id}/participantes`, {
      equipo_id: team.id,
      reason: "Participación confirmada para el ensayo",
    });
    teams.push(team);
  }
  await create("partidos/", {
    competicion_id: competition.id,
    temporada_id: season.id,
    equipo_local_id: teams[0].id,
    equipo_visitante_id: teams[1].id,
    fecha: "2026-09-01T20:00:00Z",
    marcador_local: 2,
    marcador_visitante: 1,
    estado: "finalizado",
  });
  await page.getByRole("button", { name: "Datos", exact: true }).click();
  const area = page.getByRole("region", {
    name: "Automatización de datos",
    exact: true,
  });
  await area.getByRole("tab", { name: "Reglas deportivas" }).click();
  await area
    .getByRole("combobox", {
      name: "Temporada que quieres revisar",
      exact: true,
    })
    .selectOption(String(season.id));
  await area
    .getByLabel("Nombre del reglamento")
    .fill("Regla verificada de ensayo");
  await area
    .getByLabel("Enlace al reglamento o comunicación oficial")
    .fill("https://example.test/reglamento-qa");
  await area
    .getByLabel(
      "He contrastado estos puntos, desempates y ámbito con el reglamento enlazado.",
    )
    .check();
  await area
    .getByRole("button", { name: "Guardar versión de reglamento" })
    .click();
  await expect(area.locator(".once-automation-success")).toContainText(
    "Versión de reglamento guardada",
  );
  const projection = await (
    await page.request.get(`/api/public/temporadas/${season.id}/clasificacion`)
  ).json();
  expect(projection.status).toBe("ready");
  expect(projection.rule.version).toBe(1);
  expect(projection.calculated.rows[0].points).toBe(3);
  await page.goto(`/explore/competiciones/${competition.id}`);
  await page
    .getByRole("navigation", { name: "Secciones de la competición" })
    .getByRole("button", { name: "Clasificación", exact: true })
    .click();
  await expect(
    page.getByRole("table", { name: "Tabla de posiciones" }),
  ).toContainText(teams[0].nombre);
  await page
    .getByRole("button", { name: "Tabla de la fuente", exact: true })
    .click();
  await expect(
    page.getByText(
      "No se ha recibido una tabla de la fuente para esta selección.",
    ),
  ).toBeVisible();
});
