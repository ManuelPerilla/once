import assert from "node:assert/strict";
import { test } from "node:test";
import { defaultStandingSelection } from "./public/standingSelection.js";

test("defaults open an available provider table with its exact phase and group", () => {
  assert.deepEqual(
    defaultStandingSelection({
      phases: [{ id: 1 }, { id: 2 }],
      groups: [{ id: 3, fase_id: 2 }],
      available_standings: [
        { phase_id: 1, sources: ["calculated"] },
        { phase_id: 2, group_id: 3, sources: ["official"] },
      ],
    }),
    { phase: "2", group: "3", source: "official" },
  );
});

test("calculated-only and older contexts retain an honest calculated default", () => {
  assert.deepEqual(
    defaultStandingSelection({
      phases: [{ id: 1 }],
      groups: [],
      available_standings: [{ phase_id: 1, sources: ["calculated"] }],
    }),
    { phase: "1", group: "", source: "calculated" },
  );
  assert.deepEqual(defaultStandingSelection({ phases: [], groups: [] }), {
    phase: "",
    group: "",
    source: "calculated",
  });
});

test("a default cannot select a phase or group outside the current season context", () => {
  assert.deepEqual(
    defaultStandingSelection({
      phases: [{ id: 1 }],
      groups: [{ id: 3, fase_id: 1 }],
      available_standings: [
        { phase_id: 2, group_id: 3, sources: ["official"] },
        { phase_id: 1, group_id: 99, sources: ["official"] },
      ],
    }),
    { phase: "", group: "", source: "calculated" },
  );
});
