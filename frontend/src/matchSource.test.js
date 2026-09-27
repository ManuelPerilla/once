import assert from "node:assert/strict";
import { test } from "node:test";
import {
  matchSourceLabel,
  sourceVerificationDate,
} from "./components/football/matchSource.js";

test("match provenance distinguishes manual records, API data and open archives", () => {
  assert.equal(matchSourceLabel({ provider: "manual" }), "Registro manual");
  assert.equal(matchSourceLabel({ provider: "api-football" }), "API-Football");
  assert.equal(
    matchSourceLabel({ provider: "openfootball" }),
    "Archivo abierto",
  );
});

test("older match payloads never imply verification or API coverage", () => {
  for (const source of [undefined, null, {}, { provider: "unknown" }]) {
    assert.equal(matchSourceLabel(source), "Origen sin confirmar");
    assert.equal(sourceVerificationDate(source), null);
  }
  assert.equal(sourceVerificationDate({ verified_at: "invalid" }), null);
  assert.ok(sourceVerificationDate({ verified_at: "2026-09-27T20:00:00Z" }));
});
