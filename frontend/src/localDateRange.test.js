import test from "node:test";
import assert from "node:assert/strict";
import { localDateRange } from "./lib/localDateRange.js";

function inTimezone(zone, run) {
  const previous = process.env.TZ;
  process.env.TZ = zone;
  try {
    run();
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
}

test("local date filters include the entire Colombian day and cross year boundaries", () => {
  inTimezone("America/Bogota", () => {
    assert.deepEqual(localDateRange("2025-12-31", "2025-12-31"), {
      date_start: "2025-12-31T05:00:00.000Z",
      date_end: "2026-01-01T05:00:00.000Z",
    });
  });
});

test("local day boundaries honor shorter and longer daylight-saving days", () => {
  inTimezone("America/New_York", () => {
    const spring = localDateRange("2026-03-08", "2026-03-08");
    const autumn = localDateRange("2026-11-01", "2026-11-01");
    assert.deepEqual(spring, {
      date_start: "2026-03-08T05:00:00.000Z",
      date_end: "2026-03-09T04:00:00.000Z",
    });
    assert.deepEqual(autumn, {
      date_start: "2026-11-01T04:00:00.000Z",
      date_end: "2026-11-02T05:00:00.000Z",
    });
  });
});

test("empty or invalid date bounds do not invent a date filter", () => {
  assert.deepEqual(localDateRange("", "invalid"), {
    date_start: undefined,
    date_end: undefined,
  });
});
