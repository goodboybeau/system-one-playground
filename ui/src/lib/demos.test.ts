import { describe, expect, it } from "vitest";

import { active, add, blankEditor, duplicate, load, makeDemo, remove, rename, restore, select, STORAGE_KEY, uniqueName, update, type Demos } from "./demos";
import { fromWire } from "./request";

const req = { state: "hi", questions: { q: { type: "noul" as const, instructions: "Greeting?" } } };

function three(): Demos {
  const a = makeDemo("A", fromWire(req));
  const b = makeDemo("B", fromWire(req));
  const c = makeDemo("C", fromWire(req));
  return { list: [a, b, c], active: b.id };
}

const store = (entries: Record<string, unknown>) => ({ getItem: (k: string) => (k in entries ? JSON.stringify(entries[k]) : null) });

describe("demos", () => {
  it("names new demos uniquely", () => {
    const d = three();
    expect(uniqueName(d.list, "A")).toBe("A 2");
    expect(uniqueName(d.list, "Z")).toBe("Z");
    const withTwo = [...d.list, makeDemo("A 2", blankEditor())];
    expect(uniqueName(withTwo, "A")).toBe("A 3");
  });

  it("adds after the active demo and switches to it", () => {
    const d = three();
    const n = makeDemo("New", blankEditor());
    const out = add(d, n);
    expect(out.list.map((x) => x.name)).toEqual(["A", "B", "New", "C"]);
    expect(out.active).toBe(n.id);
  });

  it("duplicates the request and settings but not the results", () => {
    let d = three();
    const b = d.list[1]!;
    d = update(d, b.id, { engines: ["laya-en"], mode: "parallel", repeat: 5, ran: { request: req, response: { mode: "x", elapsed_ms: 1, results: [] }, at: 1 } });
    const out = duplicate(d, b.id);
    const copy = active(out);
    expect(copy.name).toBe("B copy");
    expect(copy.id).not.toBe(b.id);
    expect(copy.engines).toEqual(["laya-en"]);
    expect(copy.mode).toBe("parallel");
    expect(copy.repeat).toBe(5);
    expect(copy.ran).toBeNull();
    copy.editor.stateText = "changed";
    expect(out.list.find((x) => x.id === b.id)!.editor.stateText).toBe("hi");
  });

  it("renames, ignoring blank names and tidying whitespace", () => {
    const d = three();
    const id = d.list[0]!.id;
    expect(rename(d, id, "  Support   triage ").list[0]!.name).toBe("Support triage");
    expect(rename(d, id, "   ").list[0]!.name).toBe("A");
  });

  it("removes a demo and activates its neighbour", () => {
    const d = three();
    const { demos, removed } = remove(d, d.active);
    expect(demos.list.map((x) => x.name)).toEqual(["A", "C"]);
    expect(active(demos).name).toBe("C");
    expect(removed!.index).toBe(1);
    const last = remove(select(d, d.list[2]!.id), d.list[2]!.id).demos;
    expect(active(last).name).toBe("B");
  });

  it("never removes the last demo", () => {
    const one = { list: [makeDemo("Only", blankEditor())], active: "" };
    one.active = one.list[0]!.id;
    expect(remove(one, one.active)).toEqual({ demos: one, removed: null });
  });

  it("restores a removed demo where it was", () => {
    const d = three();
    const { demos, removed } = remove(d, d.list[0]!.id);
    const back = restore(demos, removed!);
    expect(back.list.map((x) => x.name)).toEqual(["A", "B", "C"]);
    expect(active(back).name).toBe("A");
    expect(restore(back, removed!)).toBe(back);
  });

  it("migrates the single playground saved before tabs", () => {
    const editor = fromWire(req);
    const d = load(store({ "lab.playground.editor": editor, "lab.playground.engines": ["overlap"], "lab.playground.mode": "parallel", "lab.playground.repeat": 3 }));
    expect(d.list).toHaveLength(1);
    const first = active(d);
    expect(first.name).toBe("Demo 1");
    expect(first.editor).toEqual(editor);
    expect(first).toMatchObject({ engines: ["overlap"], mode: "parallel", repeat: 3, ran: null });
  });

  it("starts fresh when nothing is saved, and survives corrupt storage", () => {
    expect(active(load(store({}))).editor.questions).toHaveLength(3);
    const corrupt = { getItem: (k: string) => (k === STORAGE_KEY ? "{not json" : null) };
    expect(load(corrupt).list).toHaveLength(1);
    expect(load(store({ [STORAGE_KEY]: { list: [], active: "x" } })).list).toHaveLength(1);
  });

  it("reloads saved demos and repairs a dangling active id", () => {
    const d = three();
    expect(load(store({ [STORAGE_KEY]: d }))).toEqual(d);
    const dangling = load(store({ [STORAGE_KEY]: { ...d, active: "gone" } }));
    expect(dangling.active).toBe(d.list[0]!.id);
  });
});
