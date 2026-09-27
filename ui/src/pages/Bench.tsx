import { useEffect, useState } from "react";

import { api, type BenchResult, type Dataset, type JobSnapshot, type OverviewSlice, type Report } from "../api";
import { BenchView } from "../components/BenchView";
import { Empty, EngineName, Progress, Seg } from "../components/common";
import { useStored } from "../hooks";
import { engineColor } from "../lib/colors";
import { ms, pct } from "../lib/format";
import { useLab } from "../state";
import { useJob } from "./useJob";

const LIMITS = [25, 50, 100, 200];

export function BenchPage() {
  const { engines, fail, label } = useLab();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [name, setName] = useStored("lab.bench.dataset", "banking10");
  const [selected, setSelected] = useStored<string[]>("lab.bench.engines", []);
  const [limit, setLimit] = useStored("lab.bench.limit", 100);
  const [tab, setTab] = useStored<"overview" | "combined">("lab.bench.tab", "overview");
  const [overview, setOverview] = useState<OverviewSlice[] | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const job = useJob("bench");
  const finished = job.snapshot?.status;

  useEffect(() => {
    api.datasets().then(setDatasets).catch(fail);
  }, [fail]);

  useEffect(() => {
    api.overview().then((o) => setOverview(o.slices)).catch(fail);
  }, [fail, finished]);

  const ds = datasets.find((d) => d.name === name) ?? datasets[0];
  const size = ds ? Math.min(limit, ds.items) : limit;
  useEffect(() => {
    if (!ds) return;
    let live = true;
    api
      .report(ds.name, size)
      .then((r) => live && setReport(r))
      .catch(fail);
    return () => {
      live = false;
    };
  }, [ds, size, fail, finished]);

  const ready = engines.filter((e) => e.run?.status === "ready");
  const chosen = selected.filter((id) => ready.some((e) => e.id === id));
  const running = job.snapshot?.status === "running";

  async function start() {
    if (!ds) return;
    try {
      job.track(await api.bench({ dataset: ds.name, engines: chosen, limit }));
    } catch (e) {
      fail(e);
    }
  }

  const jobResult = job.snapshot?.result && "dataset" in job.snapshot.result ? (job.snapshot.result as BenchResult) : null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Benchmarks</h1>
          <p>
            Run a fixed, seeded slice of a public dataset through each engine, one engine at a time so they never compete for the
            machine. Results accumulate: benchmark engines whenever they fit in memory, and the leaderboard keeps the latest result
            for each.
          </p>
        </div>
      </div>

      <div className="card card-pad stack">
        <div className="row wrap" style={{ gap: 16, alignItems: "flex-end" }}>
          <label className="field" style={{ minWidth: 280 }}>
            Dataset
            <select className="select" value={ds?.name ?? ""} onChange={(e) => setName(e.target.value)}>
              {datasets.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.title} ({d.task === "noul" ? "yes/no" : d.task}, {d.items})
                </option>
              ))}
            </select>
          </label>
          <div className="field">
            <span>Items</span>
            <Seg label="Items" value={limit} options={LIMITS.map((n) => ({ value: n, label: String(n) }))} onChange={setLimit} />
          </div>
          <span className="grow" />
          <button className="btn primary" onClick={() => void start()} disabled={running || chosen.length === 0 || !ds}>
            Run benchmark
          </button>
        </div>
        {ds && (
          <div className="small ink-2">
            {ds.description} <span className="muted">Source: {ds.source}.</span>
          </div>
        )}
        <div className="row wrap">
          {engines
            .filter((e) => e.installed)
            .map((e) => {
              const on = ready.some((r) => r.id === e.id);
              return (
                <button
                  key={e.id}
                  className="engine-chip"
                  aria-pressed={on && selected.includes(e.id)}
                  disabled={!on}
                  title={on ? undefined : "Start it on the Engines page"}
                  onClick={() => setSelected((s) => (s.includes(e.id) ? s.filter((x) => x !== e.id) : [...s, e.id]))}
                >
                  <i className="swatch" style={{ background: engineColor(e.id) }} />
                  {e.label}
                </button>
              );
            })}
        </div>
        {ready.length === 0 && (
          <div className="small muted">
            No engine is running. <a href="#/engines">Start one on the Engines page</a>, or run <code>make suite</code> to benchmark every
            engine unattended.
          </div>
        )}
      </div>

      {job.snapshot && <JobStatus job={job.snapshot} onCancel={job.cancel} label={label} />}
      {jobResult && Object.keys(jobResult.engines).length > 0 && (
        <>
          <div className="section-title">This run</div>
          <BenchView result={jobResult} />
        </>
      )}

      <div className="row spread wrap" style={{ margin: "26px 0 10px" }}>
        <div className="section-title" style={{ margin: 0 }}>
          Leaderboard across runs
        </div>
        <Seg
          label="Leaderboard view"
          value={tab}
          onChange={setTab}
          options={[
            { value: "overview", label: "All datasets" },
            { value: "combined", label: ds ? `${ds.title} · ${size}` : "This dataset" },
          ]}
        />
      </div>
      {tab === "overview" ? (
        <Overview
          slices={overview}
          onOpen={(d, n) => {
            setName(d);
            if (LIMITS.includes(n)) setLimit(n);
            setTab("combined");
          }}
        />
      ) : report && Object.keys(report.engines).length > 0 ? (
        <>
          <p className="small muted" style={{ margin: "0 0 10px" }}>
            Latest result per engine for this dataset at {size} items, merged from {report.runs.length} run
            {report.runs.length === 1 ? "" : "s"} over the same items.
          </p>
          <BenchView result={report} />
        </>
      ) : (
        <div className="card">
          <Empty title="No results for this dataset and size yet">Run a benchmark above, or pick another size.</Empty>
        </div>
      )}
    </div>
  );
}

function Overview({ slices, onOpen }: { slices: OverviewSlice[] | null; onOpen: (dataset: string, limit: number) => void }) {
  const { label, engines } = useLab();
  if (!slices) return null;
  if (slices.length === 0) {
    return (
      <div className="card">
        <Empty title="No benchmarks yet">Results from every run appear here as a matrix of engines × datasets.</Empty>
      </div>
    );
  }
  const order = engines.map((e) => e.id);
  const ids = [...new Set(slices.flatMap((s) => Object.keys(s.engines)))].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  return (
    <div className="card">
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Engine</th>
              {slices.map((s) => (
                <th key={`${s.dataset}-${s.limit}`} className="r" title={`${s.title}, ${s.limit} items`}>
                  <button className="btn ghost sm" style={{ padding: 0, height: "auto", color: "inherit", font: "inherit" }} onClick={() => onOpen(s.dataset, s.limit)}>
                    {s.title}
                    <span className="muted"> · {s.limit}</span>
                  </button>
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
                {slices.map((s) => {
                  const e = s.engines[id];
                  const best = Math.max(...Object.values(s.engines).map((x) => x.accuracy));
                  const isBest = e && e.accuracy === best && Object.keys(s.engines).length > 1;
                  return (
                    <td
                      key={`${s.dataset}-${s.limit}`}
                      className={`r${isBest ? " best" : ""}`}
                      title={e ? `ECE ${e.ece?.toFixed(3) ?? "—"} · auto@95 ${pct(e.auto_at_95, 0)} · p50 ${ms(e.p50)}` : undefined}
                    >
                      {e ? (
                        <>
                          {pct(e.accuracy, 0)}
                          <div className="small muted">{ms(e.p50)}</div>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="small muted" style={{ padding: "8px 16px 12px" }}>
        Accuracy (bold: best on that dataset) and median latency. Hover a cell for calibration; click a dataset for its full leaderboard.
      </div>
    </div>
  );
}

export function JobStatus({ job, onCancel, label }: { job: JobSnapshot; onCancel: () => void; label: (id: string) => string }) {
  const p = job.progress;
  return (
    <div className="card card-pad stack" style={{ marginTop: 14, gap: 8 }}>
      <div className="row spread">
        <div className="row">
          <strong>{job.title}</strong>
          <span className={`pill ${job.status === "running" ? "busy" : job.status === "done" ? "good" : job.status === "cancelled" ? "warn" : "bad"}`}>
            <i className="dot" />
            {job.status}
          </span>
        </div>
        {job.status === "running" && (
          <button className="btn sm danger" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      <Progress done={p.done} total={p.total} />
      <div className="small muted num row">
        {p.done} / {p.total} requests
        {job.status === "running" && p.engine && (
          <>
            {" · now "}
            <EngineName id={p.engine} label={label(p.engine)} />
          </>
        )}
      </div>
      {job.error && (
        <div className="callout bad">
          <span className="icon">✕</span>
          <div>{job.error}</div>
        </div>
      )}
    </div>
  );
}
