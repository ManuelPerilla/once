import { expect, test } from "@playwright/test";

test.use({ timezoneId: "America/Bogota" });

test("admin match context isolates editions and keeps detail sections separate on mobile", async ({
  page,
  baseURL,
}) => {
  expect(process.env.SMOKE_DISPOSABLE).toBe("1");
  expect(
    new URL(baseURL).port,
    "Fixtures require the disposable Docker QA port",
  ).toBe("18080");
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === new URL(baseURL).origin
      ? route.continue()
      : route.abort(),
  );
  const login = await page.request.post("/api/login", {
    data: {
      username: process.env.SMOKE_USERNAME,
      password: process.env.SMOKE_PASSWORD,
    },
  });
  expect(login.status()).toBe(200);
  const create = async (collection, data) => {
    const response = await page.request.post(`/api/${collection}/`, { data });
    expect(
      response.status(),
      `Creating ${collection}: ${await response.text()}`,
    ).toBe(200);
    return response.json();
  };
  const suffix = Date.now();
  const conf = await create("confederaciones", {
    nombre: `Organización ${suffix}`,
    logo: "",
  });
  const competitions = [];
  for (const label of ["Andina", "Costera"])
    competitions.push(
      await create("competiciones", {
        nombre: `Liga ${label} ${suffix}`,
        logo: "",
        tipo: "liga_nacional",
        pais: "Colombia",
        confederacion_id: conf.id,
      }),
    );
  const teams = [];
  for (const label of ["Local", "Visitante"])
    teams.push(
      await create("equipos", {
        nombre: `${label} organización ${suffix}`,
        logo: "",
        tipo: "club",
        pais: "Colombia",
        confederacion_id: conf.id,
      }),
    );
  for (const competition of competitions)
    for (const team of teams) {
      const response = await page.request.post(
        `/api/equipos/${team.id}/matricular/${competition.id}`,
      );
      expect(response.status()).toBe(200);
      expect((await response.json()).ok).toBe(true);
    }
  const seasons = [
    await create("temporadas", {
      competicion_id: competitions[0].id,
      nombre: "2025",
      activa: false,
    }),
    await create("temporadas", {
      competicion_id: competitions[0].id,
      nombre: "2026",
      activa: true,
    }),
    await create("temporadas", {
      competicion_id: competitions[1].id,
      nombre: "2026",
      activa: true,
    }),
  ];
  const phases = [
    await create("fases", {
      temporada_id: seasons[0].id,
      nombre: "Apertura andina",
      tipo: "grupo",
      orden: 1,
    }),
    await create("fases", {
      temporada_id: seasons[0].id,
      nombre: "Final andina",
      tipo: "final",
      orden: 2,
    }),
    await create("fases", {
      temporada_id: seasons[1].id,
      nombre: "Jornada nueva",
      tipo: "jornada",
      orden: 1,
    }),
    await create("fases", {
      temporada_id: seasons[2].id,
      nombre: "Jornada costera",
      tipo: "jornada",
      orden: 1,
    }),
  ];
  const matches = [];
  for (const [competition, season, phase, state, date] of [
    [
      competitions[0],
      seasons[0],
      phases[0],
      "finalizado",
      "2025-02-01T19:00:00-05:00",
    ],
    [
      competitions[0],
      seasons[0],
      phases[1],
      "finalizado",
      "2025-06-01T19:00:00-05:00",
    ],
    [
      competitions[0],
      seasons[1],
      phases[2],
      "programado",
      "2026-12-01T19:00:00-05:00",
    ],
    [
      competitions[1],
      seasons[2],
      phases[3],
      "programado",
      "2026-12-02T19:00:00-05:00",
    ],
    [competitions[0], null, null, "programado", null],
  ])
    matches.push(
      await create("partidos", {
        competicion_id: competition.id,
        temporada_id: season?.id ?? null,
        fase_id: phase?.id ?? null,
        equipo_local_id: teams[0].id,
        equipo_visitante_id: teams[1].id,
        estado: state,
        fecha: date,
        marcador_local: 2,
        marcador_visitante: 1,
      }),
    );
  const player = await create("jugadores", {
    nombre: `Jugador organización ${suffix}`,
    nacionalidad: "Colombia",
    posicion: "Delantero",
  });
  await create("estadisticas", {
    partido_id: matches[0].id,
    source: "ensayo-local",
    posesion_local: 61,
    posesion_visitante: 39,
    tiros_puerta_local: 8,
    tiros_puerta_visitante: 3,
  });
  await create("eventos", {
    partido_id: matches[0].id,
    source: "ensayo-local",
    equipo_id: teams[0].id,
    jugador_id: player.id,
    tipo: "gol",
    minuto: 12,
    detalle: "Gol de organización",
  });
  await create("alineaciones", {
    partido_id: matches[0].id,
    source: "ensayo-local",
    equipo_id: teams[0].id,
    jugador_id: player.id,
    titular: true,
    posicion: "Delantero",
    dorsal: 9,
    orden: 1,
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Partidos", exact: true }).click();
  const workspace = page.getByRole("region", { name: "Registro de partidos" });
  const competitionFilter = workspace.getByLabel("Competición del partido", {
    exact: true,
  });
  const seasonFilter = workspace.getByLabel("Temporada del partido", {
    exact: true,
  });
  const phaseFilter = workspace.getByLabel("Fase del partido", { exact: true });
  await competitionFilter.selectOption(String(competitions[0].id));
  await expect(workspace.locator(".once-match-entry")).toHaveCount(4);
  await seasonFilter.selectOption(String(seasons[0].id));
  await expect(workspace.locator(".once-match-entry")).toHaveCount(2);
  await workspace.getByLabel("Desde", { exact: true }).fill("2025-02-01");
  await workspace.getByLabel("Hasta", { exact: true }).fill("2025-02-01");
  await expect(workspace.locator(".once-match-entry")).toHaveCount(1);
  await expect(
    workspace.getByRole("button", {
      name: `Consultar partido ${matches[0].id}`,
      exact: true,
    }),
  ).toBeVisible();
  await workspace.getByLabel("Desde", { exact: true }).fill("");
  await workspace.getByLabel("Hasta", { exact: true }).fill("");
  await expect(workspace.locator(".once-match-entry")).toHaveCount(2);
  await phaseFilter.selectOption(String(phases[0].id));
  await expect(workspace.locator(".once-match-entry")).toHaveCount(1);
  await expect(
    workspace.getByRole("button", {
      name: `Consultar partido ${matches[0].id}`,
      exact: true,
    }),
  ).toBeVisible();
  await seasonFilter.selectOption(String(seasons[1].id));
  await expect(phaseFilter).toHaveValue("");
  await expect(
    phaseFilter.locator(`option[value="${phases[0].id}"]`),
  ).toHaveCount(0);
  await phaseFilter.selectOption(String(phases[2].id));
  await workspace
    .getByLabel("Equipo participante", { exact: true })
    .selectOption(String(teams[0].id));
  await competitionFilter.selectOption(String(competitions[1].id));
  await expect(seasonFilter).toHaveValue("");
  await expect(phaseFilter).toHaveValue("");
  await expect(phaseFilter).toBeDisabled();
  await expect(
    workspace.getByLabel("Equipo participante", { exact: true }),
  ).toHaveValue("");
  await expect(workspace.locator(".once-match-entry")).toHaveCount(1);
  await expect(
    workspace.getByRole("button", {
      name: `Consultar partido ${matches[3].id}`,
      exact: true,
    }),
  ).toBeVisible();
  await competitionFilter.selectOption(String(competitions[0].id));
  await seasonFilter.selectOption("unassigned");
  await expect(workspace.locator(".once-match-entry")).toHaveCount(1);
  await expect(
    workspace.getByRole("button", {
      name: `Consultar partido ${matches[4].id}`,
      exact: true,
    }),
  ).toBeVisible();
  await expect(phaseFilter).toBeDisabled();

  await seasonFilter.selectOption(String(seasons[0].id));
  await phaseFilter.selectOption(String(phases[0].id));
  await page.setViewportSize({ width: 320, height: 740 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await workspace
    .getByRole("button", {
      name: `Consultar partido ${matches[0].id}`,
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Ficha del partido",
    exact: true,
  });
  await expect(dialog.getByRole("tabpanel")).toContainText("Apertura andina");
  await expect(dialog.getByRole("tabpanel")).not.toContainText("61%");
  await dialog.getByRole("tab", { name: "Estadísticas", exact: true }).click();
  await expect(dialog.getByRole("tabpanel")).toContainText("61%");
  await expect(dialog.getByRole("tabpanel")).not.toContainText(
    "Gol de organización",
  );
  await dialog.getByRole("tab", { name: "Eventos", exact: true }).click();
  await expect(dialog.getByRole("tabpanel")).toContainText(player.nombre);
  await expect(dialog.getByRole("tabpanel")).toContainText(
    "Gol de organización",
  );
  await expect(dialog.getByRole("tabpanel")).not.toContainText("61%");
  await dialog.getByRole("tab", { name: "Alineaciones", exact: true }).click();
  await expect(dialog.getByRole("tabpanel")).toContainText(player.nombre);
  await expect(dialog.getByRole("tabpanel")).toContainText("Titulares");
  await expect(dialog.getByRole("tabpanel")).not.toContainText(
    "Gol de organización",
  );
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await dialog.getByRole("button", { name: "Cerrar formulario" }).click();

  await page
    .getByRole("button", { name: "Registrar partido", exact: true })
    .first()
    .click();
  const form = page.getByRole("dialog", {
    name: "Registrar partido",
    exact: true,
  });
  await form
    .getByLabel("Competición", { exact: true })
    .selectOption(String(competitions[0].id));
  await form.getByText("Temporada, fase y estadio").click();
  await form
    .getByLabel("Temporada", { exact: true })
    .selectOption(String(seasons[0].id));
  await form
    .getByLabel("Fase", { exact: true })
    .selectOption(String(phases[0].id));
  await form
    .getByLabel("Equipo local", { exact: true })
    .selectOption(String(teams[0].id));
  await form
    .getByLabel("Equipo visitante", { exact: true })
    .selectOption(String(teams[1].id));
  await form
    .getByLabel("Competición", { exact: true })
    .selectOption(String(competitions[1].id));
  for (const label of ["Temporada", "Fase", "Equipo local", "Equipo visitante"])
    await expect(form.getByLabel(label, { exact: true })).toHaveValue("");
  expect(
    await form.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await form.getByRole("button", { name: "Cancelar", exact: true }).click();
  const persisted = await (await page.request.get("/api/partidos/")).json();
  expect(
    persisted.filter((match) =>
      competitions.some(
        (competition) => competition.id === match.competicion_id,
      ),
    ),
  ).toHaveLength(5);
  expect(errors).toEqual([]);
});
