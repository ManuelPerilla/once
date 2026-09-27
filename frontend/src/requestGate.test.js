import test from "node:test";
import assert from "node:assert/strict";
import { createRequestGate } from "./lib/requestGate.js";

test("an older refresh cannot overwrite newer data", () => {
  const gate = createRequestGate();
  const old = gate.start("matches");
  const catalog = gate.start("catalogs");
  const latest = gate.start("matches");
  assert.equal(old.signal.aborted, true);
  assert.equal(old.current(), false);
  assert.equal(latest.current(), true);
  assert.equal(catalog.current(), true);
});

test("logout invalidates all reads, including replies from a previous session", () => {
  const gate = createRequestGate();
  const session = gate.start("session");
  const catalog = gate.start("catalogs");
  gate.cancelAll();
  const nextSession = gate.start("session");
  assert.equal(session.current(), false);
  assert.equal(catalog.current(), false);
  assert.equal(catalog.signal.aborted, true);
  assert.equal(nextSession.current(), true);
});
