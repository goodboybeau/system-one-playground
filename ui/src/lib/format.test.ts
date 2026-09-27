import { describe, expect, it } from "vitest";

import { byteTicks, bytes, ms, params, pct } from "./format";

const GB = 1024 ** 3;

describe("format", () => {
  it("uses binary units like macOS", () => {
    expect(bytes(32 * GB)).toBe("32.0 GB");
    expect(bytes(3.3 * GB)).toBe("3.30 GB");
    expect(bytes(512 * 1024 ** 2)).toBe("512 MB");
    expect(bytes(null)).toBe("—");
  });

  it("makes round byte ticks that cover the max", () => {
    const t = byteTicks(3.8 * GB);
    expect(t[0]).toBe(0);
    expect(t[t.length - 1]!).toBeGreaterThanOrEqual(3.8 * GB);
    expect(t.every((v) => Number.isInteger(v / GB))).toBe(true);
    const small = byteTicks(700 * 1024 ** 2);
    expect(small.every((v) => Number.isInteger(v / 1024 ** 2))).toBe(true);
    expect(small[small.length - 1]!).toBeGreaterThanOrEqual(700 * 1024 ** 2);
    expect(small.length).toBeLessThanOrEqual(6);
  });

  it("formats latency with sensible precision", () => {
    expect(ms(4.321)).toBe("4.32 ms");
    expect(ms(43.21)).toBe("43.2 ms");
    expect(ms(432.1)).toBe("432 ms");
    expect(ms(4321)).toBe("4.32 s");
    expect(ms(undefined)).toBe("—");
  });

  it("formats params and percents", () => {
    expect(params(421_000_000)).toBe("421M");
    expect(params(4_210_000_000)).toBe("4.2B");
    expect(pct(0.1234)).toBe("12.3%");
  });
});
