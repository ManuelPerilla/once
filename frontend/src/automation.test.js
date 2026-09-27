import assert from "node:assert/strict";
import { test } from "node:test";
import {
  canRunScope,
  remainingBudget,
  displayValue,
  humanDate,
} from "./admin/automation.js";

test("a paused global control blocks every scope, including manual checks", () => {
  for (const scope of ["paused", "observe", "automatic"])
    assert.equal(canRunScope("paused", scope), false);
  assert.equal(canRunScope("automatic", "paused"), false);
  assert.equal(canRunScope("observe", "automatic"), true);
  assert.equal(canRunScope(undefined, "automatic"), false);
});
test("quota display never reports negative capacity or confuses missing limits with zero", () => {
  assert.equal(remainingBudget(110, 100), "0 de 100 disponibles");
  assert.equal(remainingBudget(100, 100), "0 de 100 disponibles");
  assert.equal(remainingBudget(0, null), "Sin límite configurado");
});
test("audit values distinguish a known zero and false from an unknown observation", () => {
  assert.equal(displayValue(0), "0");
  assert.equal(displayValue(false), "No");
  assert.equal(displayValue(null), "Sin dato");
  assert.equal(humanDate(null), "Todavía no");
  assert.equal(humanDate("invalid"), "Sin fecha disponible");
});
