import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, type CallResult, type Preset, type WireRequest } from "../api";
import { AnswerViz, decisionKey, verdict } from "../components/AnswerViz";
import { Empty, EngineName, Seg } from "../components/common";
import { DemoTabs } from "../components/DemoTabs";
import { JsonEditor } from "../components/JsonEditor";
import { QuestionEditor } from "../components/QuestionEditor";
import { engineColor } from "../lib/colors";
import * as D from "../lib/demos";
import { bytes, ms, pct } from "../lib/format";
import { blankQuestion, fromWire, stateKind, toWire, type EditorState } from "../lib/request";
import { useLab } from "../state";

type Ran = D.Ran;

function useDemos() {
  const [demos, setDemos] = useState<D.Demos>(() => D.load(window.localStorage));
  useEffect(() => {
    try {
      localStorage.setItem(D.STORAGE_KEY, JSON.stringify(demos));
    } catch {
      try {
        localStorage.setItem(D.STORAGE_KEY, JSON.stringify({ ...demos, list: demos.list.map((d) => ({ ...d, ran: null })) }));
      } catch {
        /* storage unavailable: keep working in memory */
      }
    }
  }, [demos]);
  return [demos, setDemos] as const;
}

export function PlaygroundPage({ onSendToLoad }: { onSendToLoad: (r: WireRequest) => void }) {
  const { engines, fail } = useLab();
  const [demos, setDemos] = useDemos();
  const [view, setView] = useState<"builder" | "json">("builder");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [running, setRunning] = useState<Set<string>>(new Set());
  const [closed, setClosed] = useState<{ demo: D.Demo; index: number } | null>(null);

  useEffect(() => {
    api.presets().then(setPresets).catch(fail);
  }, [fail]);

  useEffect(() => {
    if (!closed) return;
    const t = window.setTimeout(() => setClosed(null), 8000);
    return () => window.clearTimeout(t);
  }, [closed]);

  const demo = D.active(demos);
  const id = demo.id;
  const { editor, engines: selected, mode, repeat, ran } = demo;
  const patch = useCallback((fields: Partial<Omit<D.Demo, "id">>) => setDemos((d) => D.update(d, id, fields)), [id, setDemos]);
  const setEditor = (e: EditorState) => patch({ editor: e });

  const ready = engines.filter((e) => e.run?.status === "ready");
  const readyIds = new Set(ready.map((e) => e.id));
  const chosen = selected.filter((e) => readyIds.has(e));
  const built = useMemo(() => toWire(editor), [editor]);
  const busy = running.has(id);

  async function run() {
    if (!built.request || busy) return;
    if (chosen.length === 0) {
      fail(new Error("Start an engine on the Engines page, then pick it here."));
      return;
    }
    const target = id;
    const request = built.request;
    setRunning((r) => new Set(r).add(target));
    try {
      const response = await api.compare({ request, engines: chosen, repeat, mode });
      setDemos((d) => D.update(d, target, { ran: { request, response, at: Date.now() } }));
    } catch (e) {
      fail(e);
    } finally {
      setRunning((r) => {
        const next = new Set(r);
        next.delete(target);
        return next;
      });
    }
  }

  const runRef = useRef(run);
  runRef.current = run;
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        void runRef.current();
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  function loadPreset(presetId: string) {
    const p = presets.find((x) => x.id === presetId);
    if (p) patch({ editor: fromWire(p.request), ran: null });
  }

  function closeDemo(demoId: string) {
    const { demos: next, removed } = D.remove(demos, demoId);
    if (!removed) return;
    setDemos(next);
    setClosed(removed);
  }

  const toggle = (e: string) => patch({ engines: selected.includes(e) ? selected.filter((x) => x !== e) : [...selected, e] });

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Playground</h1>
          <p>Build a structured request (state plus typed questions), send it to several engines at once, and compare answers, confidence, latency and CPU cost. Each tab is its own demo.</p>
        </div>
        <div className="row">
          <select className="select" aria-label="Load a preset" value="" onChange={(e) => loadPreset(e.target.value)} title="Replace this demo's request with a preset">
            <option value="" disabled>
              Load a preset…
            </option>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <DemoTabs
        demos={demos.list}
        active={id}
        running={running}
        presets={presets}
        closed={closed?.demo ?? null}
        onSelect={(x) => setDemos((d) => D.select(d, x))}
        onRename={(x, name) => setDemos((d) => D.rename(d, x, name))}
        onClose={closeDemo}
        onUndoClose={() => {
          if (closed) setDemos((d) => D.restore(d, closed));
          setClosed(null);
        }}
        onNewBlank={() => setDemos((d) => D.add(d, D.makeDemo(D.uniqueName(d.list, "Untitled"), D.blankEditor(), D.active(d))))}
        onDuplicate={() => setDemos((d) => D.duplicate(d, d.active))}
        onNewFromPreset={(p) => setDemos((d) => D.add(d, D.makeDemo(D.uniqueName(d.list, p.title), fromWire(p.request), D.active(d))))}
      />

      <div className="play">
        <div className="card">
          <div className="card-head">
            <h2>Request</h2>
            <Seg
              label="Editor view"
              value={view}
              options={[
                { value: "builder", label: "Builder" },
                { value: "json", label: "Raw JSON" },
              ]}
              onChange={setView}
            />
          </div>
          {view === "builder" ? <Builder key={id} editor={editor} setEditor={setEditor} /> : <RawJson key={id} editor={editor} setEditor={setEditor} />}
          {built.errors.length > 0 && (
            <div className="editor-block">
              <div className="callout warn">
                <span className="icon">!</span>
                <ul style={{ margin: 0 }}>
                  {built.errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="stack sticky">
          <div className="card card-pad stack">
            <div className="row spread">
              <strong>Engines</strong>
              <span className="small muted">{ready.length === 0 ? "none running" : `${ready.length} ready`}</span>
            </div>
            <div className="row wrap">
              {engines
                .filter((e) => e.installed)
                .map((e) => {
                  const on = readyIds.has(e.id);
                  return (
                    <button
                      key={e.id}
                      className="engine-chip"
                      aria-pressed={on && selected.includes(e.id)}
                      disabled={!on}
                      title={on ? e.architecture : `${e.label} is not running: start it on the Engines page`}
                      onClick={() => toggle(e.id)}
                    >
                      <i className="swatch" style={{ background: engineColor(e.id) }} />
                      {e.label}
                    </button>
                  );
                })}
            </div>
            {ready.length === 0 ? (
              <div className="small muted">
                No engine is running. <a href="#/engines">Start one on the Engines page.</a>
              </div>
            ) : (
              chosen.length === 0 && <div className="small muted">Pick one or more of the running engines above.</div>
            )}
            <div className="row wrap spread">
              <div className="row">
                <Seg
                  label="Run mode"
                  value={mode}
                  options={[
                    { value: "sequential", label: "One at a time" },
                    { value: "parallel", label: "In parallel" },
                  ]}
                  onChange={(m) => patch({ mode: m })}
                />
                <label className="row small ink-2" title="Send the same request several times to get a latency distribution">
                  repeat
                  <input
                    className="input sm num"
                    style={{ width: 52 }}
                    type="number"
                    min={1}
                    max={50}
                    value={repeat}
                    onChange={(e) => patch({ repeat: Math.max(1, Math.min(50, Number(e.target.value) || 1)) })}
                  />
                </label>
              </div>
              <div className="row">
                <button className="btn" disabled={!built.request} onClick={() => built.request && onSendToLoad(built.request)} title="Use this request in a load test">
                  Load test…
                </button>
                <button className="btn primary" onClick={() => void run()} disabled={busy || !built.request || chosen.length === 0}>
                  {busy ? "Running…" : "Run"} <kbd>⌘↵</kbd>
                </button>
              </div>
            </div>
            {mode === "parallel" && chosen.length > 1 && (
              <div className="small muted">In parallel, engines share the CPU and GPU, so latencies include contention.</div>
            )}
          </div>

          {ran ? (
            <Results ran={ran} />
          ) : (
            <div className="card">
              <Empty title="No results yet">Pick one or more running engines and press Run.</Empty>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Builder({ editor, setEditor }: { editor: EditorState; setEditor: (e: EditorState) => void }) {
  const kind = stateKind(editor.stateText);
  const qs = editor.questions;
  const setQ = (i: number, q: (typeof qs)[number]) => setEditor({ ...editor, questions: qs.map((x, j) => (j === i ? q : x)) });
  const move = (i: number, d: -1 | 1) => {
    const next = [...qs];
    const [q] = next.splice(i, 1);
    next.splice(i + d, 0, q!);
    setEditor({ ...editor, questions: next });
  };
  const nextId = () => {
    let n = qs.length + 1;
    while (qs.some((q) => q.id === `question_${n}`)) n++;
    return `question_${n}`;
  };
  return (
    <>
      <div className="editor-block stack" style={{ gap: 8 }}>
        <div className="row spread">
          <strong>State</strong>
          <span className={`pill ${kind === "invalid-json" ? "bad" : ""}`}>
            {kind === "json" ? "JSON" : kind === "text" ? "text" : "invalid JSON"}
          </span>
        </div>
        <JsonEditor label="State" value={editor.stateText} onChange={(stateText) => setEditor({ ...editor, stateText })} asJson={kind !== "text"} />
        <span className="hint">Plain text, or a JSON object / array. Engines see the same thing either way.</span>
      </div>
      <div className="editor-block">
        <div className="row spread" style={{ marginBottom: 10 }}>
          <strong>Questions</strong>
          <span className="small muted">{qs.length} · answered in one pass</span>
        </div>
        {qs.map((q, i) => (
          <QuestionEditor
            key={q.key}
            q={q}
            onChange={(nq) => setQ(i, nq)}
            onRemove={() => setEditor({ ...editor, questions: qs.filter((_, j) => j !== i) })}
            onMove={(d) => move(i, d)}
            first={i === 0}
            last={i === qs.length - 1}
          />
        ))}
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn sm" onClick={() => setEditor({ ...editor, questions: [...qs, blankQuestion("choice", nextId())] })}>
            + Choice
          </button>
          <button className="btn sm" onClick={() => setEditor({ ...editor, questions: [...qs, { ...blankQuestion("score", nextId()), levels: ["low", "medium", "high"] }] })}>
            + Score
          </button>
          <button className="btn sm" onClick={() => setEditor({ ...editor, questions: [...qs, blankQuestion("noul", nextId())] })}>
            + Yes / no
          </button>
        </div>
      </div>
    </>
  );
}

function RawJson({ editor, setEditor }: { editor: EditorState; setEditor: (e: EditorState) => void }) {
  const current = useMemo(() => {
    const built = toWire(editor);
    return JSON.stringify(built.request ?? { state: editor.stateText, questions: {} }, null, 2);
  }, [editor]);
  const [text, setText] = useState(current);
  const [error, setError] = useState<string | null>(null);

  function apply(value: string) {
    setText(value);
    try {
      const parsed = JSON.parse(value) as WireRequest;
      if (typeof parsed !== "object" || parsed === null || typeof parsed.questions !== "object" || parsed.questions === null) {
        setError("Needs an object with \"state\" and \"questions\".");
        return;
      }
      for (const [id, q] of Object.entries(parsed.questions)) {
        if (!q || !["choice", "score", "noul"].includes((q as { type?: string }).type ?? "")) {
          setError(`questions.${id}.type must be choice, score or noul.`);
          return;
        }
      }
      setError(null);
      setEditor(fromWire(parsed));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="editor-block stack" style={{ gap: 8 }}>
      <JsonEditor label="Raw request JSON" value={text} onChange={apply} asJson minHeight="420px" maxHeight="70vh" />
      {error ? <span className="small" style={{ color: "var(--critical-text)" }}>{error}</span> : <span className="hint">The exact body sent to POST /v1/systemone. Edits sync to the builder.</span>}
    </div>
  );
}

function Results({ ran }: { ran: Ran }) {
  const { label } = useLab();
  const results = ran.response.results;
  const ok = results.filter((r) => r.status === 200 && r.answers);
  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>Engines</h2>
          <span className="small muted">
            {ran.response.mode} · {ms(ran.response.elapsed_ms)} total
          </span>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Engine</th>
                <th className="r" title="Round trip measured by the gateway">Wall</th>
                <th className="r" title="Model time inside the engine">Model</th>
                <th className="r" title="CPU time the engine process used for this request">CPU time</th>
                <th className="r">Footprint</th>
                <th className="r">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <EngineRow key={r.engine} r={r} name={label(r.engine)} />
              ))}
            </tbody>
          </table>
        </div>
        {results.some((r) => r.warnings?.length || r.status !== 200) && (
          <div className="card-pad stack" style={{ gap: 8, paddingTop: 0 }}>
            {results
              .filter((r) => r.status !== 200)
              .map((r) => (
                <div className="callout bad" key={`e-${r.engine}`}>
                  <span className="icon">✕</span>
                  <div>
                    <b>{label(r.engine)}</b>: {r.error}
                    {r.details && (
                      <ul>
                        {r.details.map((d) => (
                          <li key={d}>{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              ))}
            {results
              .filter((r) => r.warnings?.length)
              .map((r) => (
                <div className="callout warn" key={`w-${r.engine}`}>
                  <span className="icon">!</span>
                  <div>
                    <b>{label(r.engine)}</b> did not see the whole state:
                    <ul>
                      {r.warnings!.map((w) => (
                        <li key={w}>{w}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>

      {Object.entries(ran.request.questions).map(([qid, q]) => {
        const answered = ok.filter((r) => r.answers?.[qid]);
        const keys = new Set(answered.map((r) => decisionKey(r.answers![qid]!)));
        return (
          <div className="card answer-card" key={qid}>
            <div className="answer-q">
              <div>
                <h3>
                  <span className="mono">{qid}</span> <span className="tag">{q.type === "noul" ? "yes/no" : q.type}</span>
                </h3>
                {q.instructions !== undefined && <div className="instr">{String(q.instructions)}</div>}
              </div>
              {answered.length > 1 && (
                <span className={`agree pill ${keys.size === 1 ? "good" : "warn"}`}>
                  <i className="dot" />
                  {keys.size === 1 ? "all agree" : `${keys.size} different answers`}
                </span>
              )}
            </div>
            {answered.map((r) => {
              const a = r.answers![qid]!;
              return (
                <div className="engine-answer" key={r.engine}>
                  <div className="engine-answer-head">
                    <span className="who">
                      <EngineName id={r.engine} label={label(r.engine)} />
                    </span>
                    <span>
                      <span className="verdict">{verdict(a)}</span>{" "}
                      <span className="small muted num" title="Probability on the chosen answer · standardised confidence (TypeSafe's definition)">
                        p {pct(a.p_top, 0)} · conf {a.confidence.toFixed(2)}
                      </span>
                    </span>
                  </div>
                  <AnswerViz answer={a} engine={r.engine} question={q} />
                </div>
              );
            })}
          </div>
        );
      })}

      <details className="raw card" style={{ marginTop: 14 }}>
        <summary>Raw responses</summary>
        <pre className="log">{JSON.stringify(results, null, 2)}</pre>
      </details>
    </>
  );
}

function EngineRow({ r, name }: { r: CallResult; name: string }) {
  const rep = r.repeat;
  const many = rep && rep.n > 1;
  return (
    <tr>
      <td>
        <EngineName id={r.engine} label={name} />
        {r.device && <span className="small muted"> · {r.device}</span>}
        {r.status !== 200 && <span className="pill bad" style={{ marginLeft: 6 }}>HTTP {r.status || "—"}</span>}
      </td>
      <td className="r" title={many ? `p50 over ${rep.ok} runs; p95 ${ms(rep.wall.p95)}` : undefined}>
        {many ? ms(rep.wall.p50) : ms(r.wall_ms)}
        {many && <div className="small muted">p95 {ms(rep.wall.p95)}</div>}
      </td>
      <td className="r">
        {many ? ms(rep.infer.p50) : ms(r.timing?.infer_ms)}
      </td>
      <td className="r">{many ? ms(rep.cpu.p50) : ms(r.cpu_ms)}</td>
      <td className="r">{bytes(r.footprint)}</td>
      <td className="r">{r.usage?.input_tokens ?? "—"}</td>
    </tr>
  );
}
