export function defaultStandingSelection(context) {
  const available = (context.available_standings || []).filter((scope) => {
    if (!scope.phase_id) return !scope.group_id;
    if (!context.phases.some((phase) => phase.id === scope.phase_id))
      return false;
    return (
      !scope.group_id ||
      context.groups.some(
        (group) =>
          group.id === scope.group_id && group.fase_id === scope.phase_id,
      )
    );
  });
  const official = available.find((scope) =>
    scope.sources?.includes("official"),
  );
  const selected =
    official ||
    available.find((scope) => scope.sources?.includes("calculated"));
  return {
    phase: selected?.phase_id ? String(selected.phase_id) : "",
    group: selected?.group_id ? String(selected.group_id) : "",
    source: official ? "official" : "calculated",
  };
}
