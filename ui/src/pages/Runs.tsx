import { useState } from "react";

import { api, type BenchResult, type LoadResult, type RunRow } from "../api";
import { BenchView } from "../components/BenchView";
import { Empty } from "../components/common";
import { LoadView } from "../components/LoadView";
import { usePoll } from "../hooks";
import { ago, secs } from "../lib/format";
import { useLab } from "../state";

export function RunsPage() {
  const { fail } = useLab();
  const runs = usePoll(api.runs, 4000);
  const [open, setOpen] = useState<RunRow | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);

  async function show(id: string) {
    try {
      setOpen(await api.run(id));
    } catch (e) {
      fail(e);
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteRun(id);
      if (open?.id === id) setOpen(null);
      setConfirm(null);
      runs.refresh();
    } catch (e) {
      fail(e);
    }
  }

  const list = runs.data ?? [];
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p>Every benchmark and load test is saved in <code>.run/lab.db</code>. Open one to see its full results again.</p>
        </div>
      </div>

      {open ? (
        <div className="stack" style={{ gap: 14 }}>
          <div className="row">
            <button className="btn" onClick={() => setOpen(null)}>
              ← All runs
            </button>
            <strong className="grow">{open.title}</strong>
            <span className="muted small">{new Date(open.created * 1000).toLocaleString()}</span>
          </div>
          {open.result?.error && (
            <div className="callout bad">
              <span className="icon">✕</span>
              <div>{open.result.error}</div>
            </div>
          )}
          {open.status === "cancelled" && (
            <div className="callout warn">
              <span className="icon">!</span>
              <div>This run was cancelled; results cover what finished.</div>
            </div>
          )}
          {open.result && open.kind === "bench" && Object.keys((open.result as BenchResult).engines ?? {}).length > 0 && <BenchView result={open.result as BenchResult} />}
          {open.result && open.kind === "loadtest" && ((open.result as LoadResult).levels ?? []).length > 0 && <LoadView result={open.result as LoadResult} />}
          {!open.result && <div className="card"><Empty title="No results were saved for this run." /></div>}
        </div>
      ) : list.length === 0 ? (
        <div className="card">
          <Empty title="No runs yet">Benchmarks and load tests appear here when they finish.</Empty>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th className="r">Duration</th>
                  <th className="r">When</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button className="btn ghost sm" style={{ padding: 0, height: "auto", fontWeight: 600 }} onClick={() => void show(r.id)}>
                        {r.title}
                      </button>
                    </td>
                    <td>{r.kind === "bench" ? "benchmark" : "load test"}</td>
                    <td>
                      <span className={`pill ${r.status === "done" ? "good" : r.status === "running" ? "busy" : r.status === "cancelled" ? "warn" : "bad"}`}>
                        <i className="dot" />
                        {r.status}
                      </span>
                    </td>
                    <td className="r">{r.finished ? secs(r.finished - r.created) : "—"}</td>
                    <td className="r muted">{ago(r.created)}</td>
                    <td className="r">
                      {confirm === r.id ? (
                        <span className="row" style={{ justifyContent: "flex-end" }}>
                          <button className="btn sm danger" onClick={() => void remove(r.id)}>
                            Delete
                          </button>
                          <button className="btn sm ghost" onClick={() => setConfirm(null)}>
                            Keep
                          </button>
                        </span>
                      ) : (
                        <button className="btn sm ghost" aria-label={`Delete ${r.title}`} onClick={() => setConfirm(r.id)} disabled={r.status === "running"}>
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
