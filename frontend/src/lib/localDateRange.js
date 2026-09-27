function midnight(value, nextDay = false) {
  if (!value) return undefined;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return undefined;
  if (nextDay) date.setDate(date.getDate() + 1);
  return date.toISOString();
}

export function localDateRange(from, to) {
  return { date_start: midnight(from), date_end: midnight(to, true) };
}
