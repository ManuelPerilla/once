const compare = (a, b) =>
  String(a || "").localeCompare(String(b || ""), "es", { numeric: true });
export const contextModuleNames = {
  temporadas: {
    title: "Temporadas",
    singular: "temporada",
    create: "Nueva temporada",
    description:
      "Cada edición pertenece a una competición. Sus fases y partidos se organizan dentro de ella.",
  },
  fases: {
    title: "Fases",
    singular: "fase",
    create: "Nueva fase",
    description:
      "Ordena las jornadas, grupos o eliminatorias de una temporada concreta.",
  },
  estadios: {
    title: "Estadios",
    singular: "estadio",
    create: "Nuevo estadio",
    description: "Encuentra cada escenario por su nombre, país y ciudad.",
  },
  jugadores: {
    title: "Jugadores",
    singular: "jugador",
    create: "Nuevo jugador",
    description:
      "Organiza las fichas personales por nombre, nacionalidad y posición.",
  },
};
export const normalizeContext = (value) =>
  String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
export const emptyContextFilters = () => ({
  search: "",
  competition: "",
  season: "",
  country: "",
  city: "",
  position: "",
  active: "",
});

export function changeContextFilter(filters, name, value) {
  return {
    ...filters,
    [name]: value,
    ...(name === "competition" ? { season: "" } : {}),
    ...(name === "country" ? { city: "" } : {}),
  };
}

export const contextOptions = (records, key) =>
  [...new Set(records.map((record) => record[key]).filter(Boolean))].sort(
    compare,
  );

export function contextRelations(data) {
  const competitions = new Map(
    (data.competiciones || []).map((item) => [String(item.id), item]),
  );
  const seasons = new Map(
    (data.temporadas || []).map((item) => [String(item.id), item]),
  );
  return { competitions, seasons };
}

export function filterContext(module, records, filters, data) {
  const { competitions, seasons } = contextRelations(data);
  const query = normalizeContext(filters.search);
  return records
    .filter((record) => {
      const season =
        module === "fases" ? seasons.get(String(record.temporada_id)) : null;
      const competitionId =
        module === "temporadas"
          ? record.competicion_id
          : season?.competicion_id;
      const competition = competitions.get(String(competitionId));
      if (filters.competition && String(competitionId) !== filters.competition)
        return false;
      if (filters.season && String(record.temporada_id) !== filters.season)
        return false;
      if (filters.active && String(record.activa) !== filters.active)
        return false;
      if (
        filters.country &&
        (module === "jugadores" ? record.nacionalidad : record.pais) !==
          filters.country
      )
        return false;
      if (filters.city && record.ciudad !== filters.city) return false;
      if (filters.position && record.posicion !== filters.position)
        return false;
      return (
        !query ||
        normalizeContext(
          [
            record.nombre,
            record.nombre_completo,
            record.ciudad,
            record.pais,
            record.nacionalidad,
            record.posicion,
            competition?.nombre,
            season?.nombre,
          ]
            .filter(Boolean)
            .join(" "),
        ).includes(query)
      );
    })
    .sort((a, b) => {
      if (module === "fases") {
        const aSeason = seasons.get(String(a.temporada_id));
        const bSeason = seasons.get(String(b.temporada_id));
        return (
          compare(
            competitions.get(String(aSeason?.competicion_id))?.nombre,
            competitions.get(String(bSeason?.competicion_id))?.nombre,
          ) ||
          compare(aSeason?.nombre, bSeason?.nombre) ||
          a.orden - b.orden ||
          compare(a.nombre, b.nombre)
        );
      }
      return compare(a.nombre, b.nombre);
    });
}

export function contextPayload(module, values) {
  const optional = (key) => values[key]?.trim() || null;
  const payload = { nombre: values.nombre.trim() };
  if (!payload.nombre) throw new Error("Escribe un nombre para el registro.");
  if (module === "temporadas") {
    if (!values.competicion_id) throw new Error("Elige una competición.");
    if (
      values.fecha_inicio &&
      values.fecha_fin &&
      values.fecha_inicio > values.fecha_fin
    )
      throw new Error("La fecha de fin debe ser igual o posterior al inicio.");
    return {
      ...payload,
      competicion_id: Number(values.competicion_id),
      fecha_inicio: optional("fecha_inicio"),
      fecha_fin: optional("fecha_fin"),
      activa: values.activa === true,
    };
  }
  if (module === "fases") {
    if (!values.temporada_id) throw new Error("Elige una temporada.");
    const order = Number(values.orden || 0);
    if (!Number.isInteger(order) || order < 0)
      throw new Error(
        "El orden debe ser un número entero igual o mayor que cero.",
      );
    return {
      ...payload,
      temporada_id: Number(values.temporada_id),
      tipo: values.tipo || "jornada",
      orden: order,
    };
  }
  if (module === "estadios") {
    const coordinates = {};
    for (const [key, limit] of [
      ["latitud", 90],
      ["longitud", 180],
    ]) {
      const value =
        values[key] === "" || values[key] == null ? null : Number(values[key]);
      if (
        value !== null &&
        (!Number.isFinite(value) || Math.abs(value) > limit)
      )
        throw new Error(`La ${key} debe estar entre -${limit} y ${limit}.`);
      coordinates[key] = value;
    }
    return {
      ...payload,
      ciudad: optional("ciudad"),
      pais: optional("pais"),
      ...coordinates,
    };
  }
  if (module === "jugadores")
    return {
      ...payload,
      nombre_completo: optional("nombre_completo"),
      posicion: optional("posicion"),
      nacionalidad: optional("nacionalidad"),
      fecha_nacimiento: optional("fecha_nacimiento"),
    };
  throw new Error("Este módulo no permite crear registros.");
}
