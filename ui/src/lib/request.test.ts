import { describe, expect, it } from "vitest";

import type { WireRequest } from "../api";
import { blankQuestion, fromWire, stateKind, textToState, toWire } from "./request";

const REQ: WireRequest = {
  state: { subject: "Charged twice", body: "refund please" },
  questions: {
    team: { type: "choice", instructions: "Which team?", criteria: { billing: "refunds", tech: null } },
    urgency: { type: "score", instructions: "How urgent?", criteria: ["low", "high"] },
    refund: { type: "noul", instructions: "Refund?" },
    damaged: { type: "noul", criteria: { true: "arrived damaged" } },
  },
};

describe("request editor model", () => {
  it("round-trips a wire request", () => {
    const { request, errors } = toWire(fromWire(REQ));
    expect(errors).toEqual([]);
    expect(request).toEqual(REQ);
  });

  it("accepts list criteria for choice", () => {
    const ed = fromWire({ state: "x", questions: { k: { type: "choice", criteria: ["a", "b"] } } });
    expect(ed.questions[0]!.options).toEqual([
      { label: "a", description: "" },
      { label: "b", description: "" },
    ]);
    expect(toWire(ed).request!.questions.k!.criteria).toEqual({ a: null, b: null });
  });

  it("keeps non-string descriptions as JSON text", () => {
    const ed = fromWire({ state: "x", questions: { k: { type: "choice", criteria: { a: { what: "x" }, b: null } } } });
    expect(ed.questions[0]!.options[0]!.description).toBe('{"what":"x"}');
  });

  it("sends text state as a string and JSON state as an object", () => {
    expect(textToState("hello {")).toBe("hello {");
    expect(textToState(' {"a": 1} ')).toEqual({ a: 1 });
    expect(textToState("[1, 2]")).toEqual([1, 2]);
    expect(stateKind('{"a":')).toBe("invalid-json");
    expect(stateKind("plain")).toBe("text");
  });

  it("reports every problem at once", () => {
    const bad = blankQuestion("choice", "dup");
    const dup = { ...blankQuestion("score", "dup"), levels: ["only"] };
    const noul = blankQuestion("noul", "yes");
    const { request, errors } = toWire({ stateText: '{"broken":', questions: [bad, dup, noul] });
    expect(request).toBeNull();
    expect(errors).toEqual([
      "State looks like JSON but does not parse.",
      "dup: every option needs a label.",
      "dup: option labels must be unique.",
      'Question id "dup" is used twice.',
      "dup: a score needs 2-10 levels.",
      "yes: a yes/no question needs instructions or criteria.",
    ]);
  });

  it("requires state and a question", () => {
    expect(toWire({ stateText: "  ", questions: [] }).errors).toEqual(["State is empty.", "Add at least one question."]);
  });

  it("trims ids, labels and levels", () => {
    const q = { ...blankQuestion("choice", " team "), options: [{ label: " a ", description: " x " }, { label: "b", description: "" }] };
    expect(toWire({ stateText: "s", questions: [q] }).request).toEqual({
      state: "s",
      questions: { team: { type: "choice", criteria: { a: "x", b: null } } },
    });
  });
});
