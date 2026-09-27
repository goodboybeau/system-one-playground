import type { CompareResponse, WireRequest } from "../api";
import { blankQuestion, fromWire, type EditorState } from "./request";

export type Ran = { request: WireRequest; response: CompareResponse; at: number };
export type Mode = "sequential" | "parallel";

export type Demo = {
  id: string;
  name: string;
  editor: EditorState;
  engines: string[];
  mode: Mode;
  repeat: number;
  ran: Ran | null;
};

export type Demos = { list: Demo[]; active: string };

export const STARTER: WireRequest = {
  state: { subject: "Charged twice for March", body: "We were billed twice for invoice #4411. Please refund the duplicate today or we'll cancel." },
  questions: {
    team: { type: "choice", instructions: "Which team should handle this?", criteria: { billing: "invoices, refunds", technical: "bugs, outages", sales: "pricing, upgrades" } },
    urgency: { type: "score", instructions: "How urgent is this?", criteria: ["not urgent", "can wait a day", "today", "emergency"] },
    churn: { type: "noul", instructions: "Is the customer threatening to leave?" },
  },
};

let counter = 0;
const newId = () => `d${Date.now().toString(36)}${(counter++).toString(36)}`;

export function uniqueName(list: Demo[], base: string): string {
  const taken = new Set(list.map((d) => d.name));
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base} ${n}`)) n++;
  return `${base} ${n}`;
}

export function makeDemo(name: string, editor: EditorState, from?: Partial<Pick<Demo, "engines" | "mode" | "repeat">>): Demo {
  return { id: newId(), name, editor, engines: from?.engines ?? [], mode: from?.mode ?? "sequential", repeat: from?.repeat ?? 1, ran: null };
}

export function blankEditor(): EditorState {
  return { stateText: "", questions: [blankQuestion("choice", "question_1")] };
}

export function active(d: Demos): Demo {
  return d.list.find((x) => x.id === d.active) ?? d.list[0]!;
}

/** Adds a demo right after the active one and switches to it. */
export function add(d: Demos, demo: Demo): Demos {
  const at = d.list.findIndex((x) => x.id === d.active);
  const list = [...d.list];
  list.splice(at < 0 ? list.length : at + 1, 0, demo);
  return { list, active: demo.id };
}

/** A copy of the request and settings; results stay with the original. */
export function duplicate(d: Demos, id: string): Demos {
  const src = d.list.find((x) => x.id === id);
  if (!src) return d;
  const copy = makeDemo(uniqueName(d.list, `${src.name} copy`), structuredClone(src.editor), src);
  return add({ ...d, active: id }, copy);
}

export function rename(d: Demos, id: string, name: string): Demos {
  const clean = name.trim().replace(/\s+/g, " ").slice(0, 60);
  if (!clean) return d;
  return { ...d, list: d.list.map((x) => (x.id === id ? { ...x, name: clean } : x)) };
}

export function update(d: Demos, id: string, patch: Partial<Omit<Demo, "id">>): Demos {
  return { ...d, list: d.list.map((x) => (x.id === id ? { ...x, ...patch } : x)) };
}

export function select(d: Demos, id: string): Demos {
  return d.list.some((x) => x.id === id) ? { ...d, active: id } : d;
}

/** Removes a demo; the last one can't be removed. The neighbour to the right (else left) becomes active. */
export function remove(d: Demos, id: string): { demos: Demos; removed: { demo: Demo; index: number } | null } {
  const index = d.list.findIndex((x) => x.id === id);
  if (index < 0 || d.list.length === 1) return { demos: d, removed: null };
  const list = d.list.filter((x) => x.id !== id);
  const nextActive = d.active === id ? (list[index] ?? list[index - 1]!).id : d.active;
  return { demos: { list, active: nextActive }, removed: { demo: d.list[index]!, index } };
}

export function restore(d: Demos, removed: { demo: Demo; index: number }): Demos {
  if (d.list.some((x) => x.id === removed.demo.id)) return d;
  const list = [...d.list];
  list.splice(Math.min(removed.index, list.length), 0, removed.demo);
  return { list, active: removed.demo.id };
}

function isDemos(v: unknown): v is Demos {
  if (!v || typeof v !== "object") return false;
  const d = v as Demos;
  return (
    Array.isArray(d.list) &&
    d.list.length > 0 &&
    typeof d.active === "string" &&
    d.list.every((x) => x && typeof x.id === "string" && typeof x.name === "string" && x.editor && Array.isArray(x.editor.questions))
  );
}

function read<T>(storage: Pick<Storage, "getItem">, key: string): T | null {
  try {
    const raw = storage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export const STORAGE_KEY = "lab.demos.v1";

/** Loads saved demos, or builds the first one from the single-playground settings saved before tabs existed. */
export function load(storage: Pick<Storage, "getItem">): Demos {
  const saved = read<unknown>(storage, STORAGE_KEY);
  if (isDemos(saved)) return saved.list.some((x) => x.id === saved.active) ? saved : { ...saved, active: saved.list[0]!.id };
  const editor = read<EditorState>(storage, "lab.playground.editor");
  const first = makeDemo("Demo 1", editor && Array.isArray(editor.questions) ? editor : fromWire(STARTER), {
    engines: read<string[]>(storage, "lab.playground.engines") ?? [],
    mode: read<Mode>(storage, "lab.playground.mode") === "parallel" ? "parallel" : "sequential",
    repeat: read<number>(storage, "lab.playground.repeat") ?? 1,
  });
  return { list: [first], active: first.id };
}
