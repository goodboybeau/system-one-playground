import { useState } from "react";

import type { WireRequest } from "./api";
import { useHashRoute } from "./hooks";
import { bytes } from "./lib/format";
import { BenchPage } from "./pages/Bench";
import { EnginesPage } from "./pages/Engines";
import { LoadPage } from "./pages/Load";
import { PlaygroundPage } from "./pages/Playground";
import { RunsPage } from "./pages/Runs";
import { LabProvider, useLab } from "./state";

const ROUTES = [
  { id: "playground", label: "Playground" },
  { id: "engines", label: "Engines" },
  { id: "bench", label: "Benchmarks" },
  { id: "load", label: "Load test" },
  { id: "runs", label: "Runs" },
] as const;

export function App() {
  return (
    <LabProvider>
      <Shell />
    </LabProvider>
  );
}

function Shell() {
  const [route, go] = useHashRoute();
  const [handoff, setHandoff] = useState<WireRequest | null>(null);
  const { engines, offline, system } = useLab();
  const running = engines.filter((e) => e.run && e.run.status !== "error" && e.run.status !== "exited").length;
  const job = system?.active_job;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
            <rect width="32" height="32" rx="7" fill="var(--ink)" />
            <path d="M9 22V10l7 6 7-6v12" fill="none" stroke="var(--surface)" strokeWidth="3" strokeLinejoin="round" />
          </svg>
          <div>
            System One Playground
            <small>Decision models, side by side</small>
          </div>
        </div>
        <nav className="nav">
          {ROUTES.map((r) => (
            <a key={r.id} href={`#/${r.id}`} aria-current={route === r.id ? "page" : undefined}>
              {r.label}
              {r.id === "engines" && running > 0 && <span className="badge">{running} on</span>}
              {r.id === "bench" && job?.kind === "bench" && <span className="badge">running</span>}
              {r.id === "load" && job?.kind === "loadtest" && <span className="badge">running</span>}
            </a>
          ))}
        </nav>
        <div className="sidebar-foot">
          {offline ? (
            <div className="callout bad small">
              <span className="icon">✕</span>
              <div>
                Gateway unreachable. Run <code>make lab</code>.
              </div>
            </div>
          ) : (
            <SystemMeter />
          )}
        </div>
      </aside>
      <main className="main">
        {route === "engines" ? (
          <EnginesPage />
        ) : route === "bench" ? (
          <BenchPage />
        ) : route === "load" ? (
          <LoadPage handoff={handoff} />
        ) : route === "runs" ? (
          <RunsPage />
        ) : (
          <PlaygroundPage
            onSendToLoad={(r) => {
              setHandoff(r);
              go("load");
            }}
          />
        )}
      </main>
    </div>
  );
}

function SystemMeter() {
  const { metrics, system } = useLab();
  const last = metrics?.system[metrics.system.length - 1];
  if (!last || !system) return null;
  const memPct = last.memory_used / last.memory_total;
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="meter">
        <div className="label">
          <span>CPU</span>
          <span className="num">{last.cpu_percent.toFixed(0)}%</span>
        </div>
        <div className="bar">
          <span style={{ width: `${Math.min(100, last.cpu_percent)}%` }} />
        </div>
      </div>
      <div className="meter">
        <div className="label">
          <span>GPU</span>
          <span className="num">{last.gpu_percent === null ? "—" : `${last.gpu_percent.toFixed(0)}%`}</span>
        </div>
        <div className="bar">
          <span style={{ width: `${Math.min(100, last.gpu_percent ?? 0)}%` }} />
        </div>
      </div>
      <div className="meter">
        <div className="label">
          <span>Memory</span>
          <span className="num">
            {bytes(last.memory_used)} / {bytes(last.memory_total)}
          </span>
        </div>
        <div className="bar">
          <span style={{ width: `${memPct * 100}%`, background: memPct > 0.9 ? "var(--critical)" : memPct > 0.8 ? "var(--warning)" : undefined }} />
        </div>
      </div>
      <div className="small muted">{system.chip}</div>
    </div>
  );
}
