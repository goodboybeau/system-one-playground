import { useMemo, useState } from "react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

import type { BenchEngine, BenchResult } from "../api";
import { engineColor } from "../lib/colors";
import { bytes, ms, num, pct, preview } from "../lib/format";
import { useLab } from "../state";
import { ChartCard, Confusion, EngineBars, XYLines } from "./charts";
import { download, EngineName, Seg } from "./common";

type Col = { key: string; label: string; title: string; get: (e: BenchEngine) => number | null | undefined; fmt: (v: number | null | undefined) => string; better: "high" | "low" };

const COLS: Col[] = [
  { key: "acc", label: "Accuracy", title: "Right answers over all items; errors count as wrong", get: (e) => e.summary?.accuracy, fmt: (v) => pct(v), better: "high" },
  { key: "cov", label: "Answered", title: "Share of items the engine answered without an error", get: (e) => e.summary?.coverage, fmt: (v) => pct(v, 0), better: "high" },
  { key: "ece", label: "ECE", title: "Expected calibration error over 10 confidence bins; 0 is perfectly calibrated", get: (e) => e.summary?.ece, fmt: (v) => num(v, 3), better: "low" },
  { key: "brier", label: "Brier", title: "Mean squared error of the whole probability distribution", get: (e) => e.summary?.brier, fmt: (v) => num(v, 3), better: "low" },
  { key: "w95", label: "Wrong @95%", title: "Answers that were wrong while ≥95% confident", get: (e) => e.summary?.wrong_at_95, fmt: (v) => pct(v), better: "low" },
  { key: "a95", label: "Auto @95%", title: "Share of items you could accept automatically, most confident first, keeping 95% accuracy", get: (e) => e.summary?.auto_at_95, fmt: (v) => pct(v, 0), better: "high" },
  { key: "p50", label: "p50", title: "Median round-trip latency", get: (e) => e.latency?.wall.p50, fmt: ms, better: "low" },
  { key: "p95", label: "p95", title: "95th percentile round-trip latency", get: (e) => e.latency?.wall.p95, fmt: ms, better: "low" },
  { key: "cpu", label: "CPU / req", title: "Median CPU time the engine process used per request", get: (e) => e.cpu_ms?.p50, fmt: ms, better: "low" },
  { key: "mem", label: "Peak mem", title: "Peak physical footprint during the run", get: (e) => e.resources?.footprint_peak, fmt: bytes, better: "low" },
];

function chance(result: BenchResult): number {
  const t = result.dataset.task;
  if (t === "noul") return 0.5;
  const n = result.dataset.labels?.length ?? 0;
  return n ? 1 / n : 0;
}

export function BenchView({ result }: { result: BenchResult }) {
  const { label } = useLab();
  const ids = Object.keys(result.engines);
  const ok = ids.filter((id) => result.engines[id]!.summary);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "acc", dir: -1 });
  const [confusionFor, setConfusionFor] = useState(ok[0] ?? "");
  const [calFocus, setCalFocus] = useState<string>("all");
  const calIds = calFocus === "all" || !ok.includes(calFocus) ? ok : [calFocus];

  const sorted = useMemo(() => {
    const col = COLS.find((c) => c.key === sort.key)!;
    return [...ok].sort((a, b) => ((col.get(result.engines[a]!) ?? -Infinity) - (col.get(result.engines[b]!) ?? -Infinity)) * sort.dir);
  }, [ok.join(), sort, result]);

  const best = (col: Col) => {
    const vals = ok.map((id) => col.get(result.engines[id]!)).filter((v): v is number => v !== null && v !== undefined);
    if (vals.length < 2) return null;
    return col.better === "high" ? Math.max(...vals) : Math.min(...vals);
  };

  const accRows = sorted.map((id) => ({ id, label: label(id), value: result.engines[id]!.summary!.accuracy }));
  const reliability = Array.from({ length: 10 }, (_, b) => {
    const row: Record<string, number | null> = { x: (b + 0.5) / 10 };
    for (const id of ok) {
      const bin = result.engines[id]!.summary!.reliability[b]!;
      row[id] = bin.n >= 3 ? bin.accuracy : null;
    }
    return row;
  });
  const langs = ok.some((id) => result.engines[id]!.by_lang);
  const truncated = ok.filter((id) => (result.engines[id]!.truncated ?? 0) > 0);
  const failed = ids.filter((id) => result.engines[id]!.error);

  return (
    <div className="stack" style={{ gap: 14 }}>
      {failed.map((id) => (
        <div className="callout bad" key={id}>
          <span className="icon">✕</span>
          <div>
            <b>{label(id)}</b> was skipped: {result.engines[id]!.error}
          </div>
        </div>
      ))}
      {ok.map((id) => {
        const errs = Object.entries(result.engines[id]!.errors ?? {});
        return errs.length ? (
          <div className="callout warn" key={`err-${id}`}>
            <span className="icon">!</span>
            <div>
              <b>{label(id)}</b> could not answer {errs.reduce((s, [, n]) => s + n, 0)} items; they count as wrong:
              <ul>
                {errs.map(([m, n]) => (
                  <li key={m}>
                    {n}× {m}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null;
      })}
      {truncated.length > 0 && (
        <div className="callout warn">
          <span className="icon">!</span>
          <div>
            State was cut to fit the context window on{" "}
            {truncated.map((id, i) => (
              <span key={id}>
                {i > 0 && ", "}
                <b>{label(id)}</b> ({result.engines[id]!.truncated} items)
              </span>
            ))}
            . Those engines answered without reading the whole input.
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-head">
          <h3>Leaderboard</h3>
          <button className="btn sm" onClick={() => download(`bench-${result.dataset.name}.json`, result)}>
            Export JSON
          </button>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Engine</th>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    className="r sortable"
                    title={c.title}
                    aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                    onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? (s.dir === 1 ? -1 : 1) : c.better === "high" ? -1 : 1 }))}
                  >
                    {c.label}
                    {sort.key === c.key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
                  </th>
                ))}
                {result.dataset.task === "score" && <th className="r" title="Mean absolute error of the expected level">MAE</th>}
              </tr>
            </thead>
            <tbody>
              {sorted.map((id) => {
                const e = result.engines[id]!;
                return (
                  <tr key={id}>
                    <td>
                      <EngineName id={id} label={label(id)} />
                      <span className="small muted"> · {e.device}</span>
                    </td>
                    {COLS.map((c) => {
                      const v = c.get(e);
                      const b = best(c);
                      return (
                        <td key={c.key} className={`r${b !== null && v === b ? " best" : ""}`}>
                          {c.fmt(v)}
                        </td>
                      );
                    })}
                    {result.dataset.task === "score" && <td className="r">{num(e.summary!.mae, 2)}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="small muted" style={{ padding: "8px 16px 12px" }}>
          Bold marks the best value in each column. Chance accuracy is {pct(chance(result), 0)}. Engines ran one at a time over the
          same {result.items.length} items.
        </div>
      </div>

      <div className="chart-grid">
        <ChartCard title="Accuracy" sub={`Dashed line: chance (${pct(chance(result), 0)})`}>
          <EngineBars rows={accRows} fmt={(v) => pct(v, 0)} domain={[0, 1]} reference={{ value: chance(result), label: "chance" }} />
        </ChartCard>
        <ChartCard title="Calibration" sub="Accuracy within each confidence bin (bins with ≥3 answers). On the diagonal = says what it means." legend={calIds.map((id) => ({ id, label: label(id) }))}>
          {ok.length > 3 && (
            <div className="row" style={{ marginBottom: 6 }}>
              <select className="select sm" aria-label="Engine for calibration" value={calFocus} onChange={(e) => setCalFocus(e.target.value)}>
                <option value="all">All engines</option>
                {ok.map((id) => (
                  <option key={id} value={id}>
                    {label(id)}
                  </option>
                ))}
              </select>
              <span className="small muted">Pick one engine to read its curve.</span>
            </div>
          )}
          <XYLines
            data={reliability}
            x="x"
            lines={calIds.map((id) => ({ key: id, label: label(id), color: engineColor(id) }))}
            fmt={(v) => pct(v, 0)}
            xFmt={(v) => pct(v, 0)}
            xLabel={(v) => `confidence ${pct(Number(v) - 0.05, 0)}–${pct(Number(v) + 0.05, 0)}`}
            yDomain={[0, 1]}
            xDomain={[0, 1]}
            xTicks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
            diagonal
          />
        </ChartCard>
      </div>

      {ok.length > 1 && (
        <ChartCard title="Accuracy vs latency" sub="Up and to the left is better. Median round-trip latency, log scale. Hover a point for its numbers." legend={ok.map((id) => ({ id, label: label(id) }))}>
          <Frontier result={result} ids={ok} />
        </ChartCard>
      )}

      {langs && <LangTable result={result} ids={ok} />}

      {result.dataset.task !== "noul" && confusionFor && result.engines[confusionFor]?.summary?.confusion && (
        <div className="card">
          <div className="card-head">
            <h3>Confusion matrix</h3>
            <select className="select sm" aria-label="Engine for confusion matrix" value={confusionFor} onChange={(e) => setConfusionFor(e.target.value)}>
              {ok.map((id) => (
                <option key={id} value={id}>
                  {label(id)}
                </option>
              ))}
            </select>
          </div>
          <div className="card-pad">
            <Confusion {...result.engines[confusionFor]!.summary!.confusion!} />
          </div>
        </div>
      )}

      <Items result={result} ids={ok} />
    </div>
  );
}

function Frontier({ result, ids }: { result: BenchResult; ids: string[] }) {
  const { label } = useLab();
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ScatterChart margin={{ top: 16, right: 24, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--grid)" />
        <XAxis
          type="number"
          dataKey="lat"
          scale="log"
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => ms(v)}
          stroke="var(--axis)"
          tick={{ fill: "var(--muted)", fontSize: 11 }}
          name="p50 latency"
        />
        <YAxis type="number" dataKey="acc" domain={[0, 1]} tickFormatter={(v: number) => pct(v, 0)} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 11 }} width={48} />
        <ZAxis range={[90, 90]} />
        <Tooltip
          isAnimationActive={false}
          content={({ active, payload }) => {
            const d = active && payload?.[0] ? (payload[0].payload as { name: string; acc: number; lat: number }) : null;
            return d ? (
              <div className="tooltip">
                <div className="t-head">{d.name}</div>
                <div className="t-row">
                  <span>accuracy</span>
                  <span>{pct(d.acc)}</span>
                </div>
                <div className="t-row">
                  <span>p50</span>
                  <span>{ms(d.lat)}</span>
                </div>
              </div>
            ) : null;
          }}
        />
        {ids.map((id) => {
          const e = result.engines[id]!;
          const point = { name: label(id), acc: e.summary!.accuracy, lat: Math.max(0.01, e.latency!.wall.p50 ?? 0.01) };
          return (
            <Scatter key={id} data={[point]} fill={engineColor(id)} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false} />
          );
        })}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function LangTable({ result, ids }: { result: BenchResult; ids: string[] }) {
  const { label } = useLab();
  const langs = [...new Set(ids.flatMap((id) => Object.keys(result.engines[id]!.by_lang ?? {})))].sort();
  return (
    <div className="card">
      <div className="card-head">
        <h3>Accuracy by language</h3>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Engine</th>
              {langs.map((l) => (
                <th key={l} className="r">
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => (
              <tr key={id}>
                <td>
                  <EngineName id={id} label={label(id)} />
                </td>
                {langs.map((l) => (
                  <td key={l} className="r">
                    {pct(result.engines[id]!.by_lang?.[l], 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type Filter = "all" | "disagree" | "allwrong" | "errors";

function Items({ result, ids }: { result: BenchResult; ids: string[] }) {
  const { label } = useLab();
  const [filter, setFilter] = useState<Filter>("disagree");
  const [open, setOpen] = useState<number | null>(null);
  const [limit, setLimit] = useState(50);
  const rows = result.items
    .map((it, i) => ({ it, i, answers: ids.map((id) => result.engines[id]!.answers![i]) }))
    .filter(({ answers }) => {
      if (filter === "all") return true;
      if (filter === "errors") return answers.some((a) => a?.error);
      const preds = answers.filter((a) => a && !a.error);
      if (filter === "allwrong") return preds.length > 0 && preds.every((a) => !a!.correct);
      return new Set(preds.map((a) => a!.correct)).size > 1;
    });
  const gold = (g: unknown) => (result.dataset.task === "score" && result.dataset.legend ? `${g} · ${result.dataset.legend[Number(g)]}` : String(g));

  return (
    <div className="card">
      <div className="card-head">
        <h3>Items</h3>
        <Seg<Filter>
          label="Item filter"
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setOpen(null);
          }}
          options={[
            { value: "disagree", label: "Split decisions" },
            { value: "allwrong", label: "All wrong" },
            { value: "errors", label: "Errors" },
            { value: "all", label: "All" },
          ]}
        />
      </div>
      {rows.length === 0 ? (
        <div className="empty">Nothing matches this filter.</div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Input</th>
                <th>Answer</th>
                {ids.map((id) => (
                  <th key={id}>
                    <EngineName id={id} label={label(id)} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).flatMap(({ it, i, answers }) => [
                <tr key={it.id} onClick={() => setOpen(open === i ? null : i)} style={{ cursor: "pointer" }}>
                  <td className="muted">{i + 1}</td>
                  <td className="item-state" title={typeof it.state === "string" ? it.state : undefined}>
                    {it.lang && <span className="tag" style={{ marginRight: 6 }}>{it.lang}</span>}
                    {preview(it.state, 90)}
                  </td>
                  <td className="mono">{gold(it.gold)}</td>
                  {answers.map((a, k) => (
                    <td key={ids[k]}>
                      {!a ? "—" : a.error ? (
                        <span className="bad-mark" title={a.error}>error</span>
                      ) : (
                        <span title={a.warnings?.join("\n")}>
                          <span className={a.correct ? "ok-mark" : "bad-mark"}>{a.correct ? "✓" : "✗"}</span>{" "}
                          <span className="mono">{a.predicted}</span> <span className="muted small num">{pct(a.p_top, 0)}</span>
                          {a.warnings && a.warnings.length > 0 && <span className="tag" style={{ marginLeft: 4 }}>cut</span>}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>,
                open === i ? (
                  <tr key={`${it.id}-open`}>
                    <td />
                    <td colSpan={2 + ids.length}>
                      <pre className="log" style={{ maxHeight: 220 }}>{typeof it.state === "string" ? it.state : JSON.stringify(it.state, null, 2)}</pre>
                      <div className="row wrap" style={{ gap: 18, marginTop: 8 }}>
                        {answers.map((a, k) =>
                          a && !a.error ? (
                            <div key={ids[k]} className="small">
                              <EngineName id={ids[k]!} label={label(ids[k]!)} />
                              <div className="muted num">
                                {a.top?.length
                                  ? a.top.map(([l, p]) => `${l} ${pct(p, 0)}`).join(" · ")
                                  : a.noul !== undefined
                                    ? `P(yes) ${pct(a.noul)}`
                                    : ""}
                                {" · "}
                                {ms(a.wall_ms)}
                              </div>
                            </div>
                          ) : null,
                        )}
                      </div>
                    </td>
                  </tr>
                ) : null,
              ])}
            </tbody>
          </table>
        </div>
      )}
      <div className="row spread small muted" style={{ padding: "8px 16px 12px" }}>
        <span>
          {rows.length} of {result.items.length} items · click a row for the full input and each engine's top options
        </span>
        {rows.length > limit && (
          <button className="btn sm" onClick={() => setLimit((l) => l + 100)}>
            Show more
          </button>
        )}
      </div>
    </div>
  );
}
