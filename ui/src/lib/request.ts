import type { QType, WireQuestion, WireRequest } from "../api";

export type Option = { label: string; description: string };

export type EditorQuestion = {
  key: string;
  id: string;
  type: QType;
  instructions: string;
  options: Option[];
  levels: string[];
  trueText: string;
  falseText: string;
};

export type EditorState = { stateText: string; questions: EditorQuestion[] };

let counter = 0;
export const newKey = () => `q${Date.now().toString(36)}${(counter++).toString(36)}`;

export function blankQuestion(type: QType = "choice", id = "question"): EditorQuestion {
  return {
    key: newKey(),
    id,
    type,
    instructions: "",
    options: [
      { label: "", description: "" },
      { label: "", description: "" },
    ],
    levels: ["", ""],
    trueText: "",
    falseText: "",
  };
}

const asText = (v: unknown): string => (v === null || v === undefined ? "" : typeof v === "string" ? v : JSON.stringify(v));

export function stateToText(state: unknown): string {
  return typeof state === "string" ? state : JSON.stringify(state, null, 2);
}

/** A state that parses as a JSON object or array is sent as JSON; anything else is sent as text. */
export function textToState(text: string): unknown {
  const t = text.trim();
  if (t.startsWith("{") || t.startsWith("[")) {
    try {
      return JSON.parse(t);
    } catch {
      return text;
    }
  }
  return text;
}

export function stateKind(text: string): "json" | "text" | "invalid-json" {
  const t = text.trim();
  if (!(t.startsWith("{") || t.startsWith("["))) return "text";
  try {
    JSON.parse(t);
    return "json";
  } catch {
    return "invalid-json";
  }
}

export function fromWire(req: WireRequest): EditorState {
  const questions = Object.entries(req.questions ?? {}).map(([id, q]): EditorQuestion => {
    const base = blankQuestion(q.type, id);
    base.instructions = asText(q.instructions);
    if (q.type === "choice") {
      const c = q.criteria;
      base.options = Array.isArray(c)
        ? c.map((label) => ({ label: String(label), description: "" }))
        : Object.entries((c ?? {}) as Record<string, unknown>).map(([label, d]) => ({ label, description: asText(d) }));
    } else if (q.type === "score") {
      base.levels = Array.isArray(q.criteria) ? q.criteria.map(asText) : ["", ""];
    } else {
      const c = (q.criteria ?? {}) as Record<string, unknown>;
      base.trueText = asText(c.true);
      base.falseText = asText(c.false);
    }
    return base;
  });
  return { stateText: stateToText(req.state), questions };
}

export type BuildResult = { request: WireRequest | null; errors: string[] };

export function toWire(ed: EditorState): BuildResult {
  const errors: string[] = [];
  if (stateKind(ed.stateText) === "invalid-json") errors.push("State looks like JSON but does not parse.");
  if (!ed.stateText.trim()) errors.push("State is empty.");
  if (ed.questions.length === 0) errors.push("Add at least one question.");
  const ids = new Set<string>();
  const questions: Record<string, WireQuestion> = {};
  for (const q of ed.questions) {
    const id = q.id.trim();
    const name = id || "(unnamed)";
    if (!id) errors.push("Every question needs an id.");
    else if (ids.has(id)) errors.push(`Question id "${id}" is used twice.`);
    ids.add(id);
    const wq: WireQuestion = { type: q.type };
    if (q.instructions.trim()) wq.instructions = q.instructions.trim();
    if (q.type === "choice") {
      const labels = q.options.map((o) => o.label.trim());
      if (labels.some((l) => !l)) errors.push(`${name}: every option needs a label.`);
      if (new Set(labels).size !== labels.length) errors.push(`${name}: option labels must be unique.`);
      if (labels.length < 2) errors.push(`${name}: a choice needs at least 2 options.`);
      if (labels.length > 255) errors.push(`${name}: at most 255 options.`);
      wq.criteria = Object.fromEntries(q.options.map((o) => [o.label.trim(), o.description.trim() || null]));
    } else if (q.type === "score") {
      const levels = q.levels.map((l) => l.trim());
      if (levels.some((l) => !l)) errors.push(`${name}: every level needs a description.`);
      if (levels.length < 2 || levels.length > 10) errors.push(`${name}: a score needs 2-10 levels.`);
      wq.criteria = levels;
    } else {
      const crit: Record<string, string> = {};
      if (q.trueText.trim()) crit.true = q.trueText.trim();
      if (q.falseText.trim()) crit.false = q.falseText.trim();
      if (Object.keys(crit).length) wq.criteria = crit;
      if (!q.instructions.trim() && !Object.keys(crit).length) errors.push(`${name}: a yes/no question needs instructions or criteria.`);
    }
    if (id) questions[id] = wq;
  }
  if (errors.length) return { request: null, errors };
  return { request: { state: textToState(ed.stateText), questions }, errors };
}
