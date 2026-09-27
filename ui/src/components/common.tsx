import type { EngineRun } from "../api";
import { engineColor } from "../lib/colors";

export function StatusPill({ run, remote }: { run: EngineRun | null; remote?: boolean }) {
  if (!run) return <span className="pill">{remote ? "not connected" : "stopped"}</span>;
  const s = run.status;
  if (s === "ready") return <span className="pill good"><i className="dot" />ready</span>;
  if (s === "error" || s === "exited") return <span className="pill bad"><i className="dot" />{s === "error" ? "failed" : "crashed"}</span>;
  return <span className="pill busy"><i className="dot" />{s}</span>;
}

export function EngineName({ id, label }: { id: string; label: string }) {
  return (
    <span className="row" style={{ gap: 7 }}>
      <i className="swatch" style={{ background: engineColor(id) }} />
      {label}
    </span>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  );
}

export function Progress({ done, total }: { done: number; total: number }) {
  const p = total ? Math.min(100, (done / total) * 100) : 0;
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${p}%` }} />
    </div>
  );
}

export function Seg<T extends string | number>({ value, options, onChange, label }: { value: T; options: Array<{ value: T; label: string }>; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
