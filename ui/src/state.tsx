import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { api, ApiError, type Engine, type Metrics, type SystemInfo } from "./api";
import { usePoll } from "./hooks";

type Toast = { id: number; kind: "info" | "error"; text: string; details: string[] };

type Lab = {
  engines: Engine[];
  system: SystemInfo | null;
  metrics: Metrics | null;
  offline: boolean;
  refreshEngines: () => void;
  toast: (text: string, kind?: Toast["kind"], details?: string[]) => void;
  fail: (e: unknown) => void;
  label: (id: string) => string;
};

const Ctx = createContext<Lab | null>(null);

export function useLab(): Lab {
  const lab = useContext(Ctx);
  if (!lab) throw new Error("useLab outside LabProvider");
  return lab;
}

const WINDOW_S = 300;

export function LabProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const engines = usePoll(api.engines, 1500);
  const system = usePoll(api.system, 3000);

  const acc = useRef<Metrics | null>(null);
  const metrics = usePoll(async () => {
    const prev = acc.current;
    const since = prev ? prev.now - 0.001 : Date.now() / 1000 - WINDOW_S;
    const m = await api.metrics(since);
    const cutoff = m.now - WINDOW_S;
    const merged: Metrics = {
      now: m.now,
      system: [...(prev?.system ?? []), ...m.system].filter((s) => s.t > cutoff),
      engines: {},
    };
    for (const [id, e] of Object.entries(m.engines)) {
      const old = prev?.engines[id]?.samples ?? [];
      const lastT = old.length ? old[old.length - 1]!.t : 0;
      merged.engines[id] = { status: e.status, samples: [...old, ...e.samples.filter((s) => s.t > lastT)].filter((s) => s.t > cutoff) };
    }
    acc.current = merged;
    return merged;
  }, 1000);

  const toast = useCallback((text: string, kind: Toast["kind"] = "info", details: string[] = []) => {
    const id = nextId.current++;
    setToasts((t) => [...t.slice(-3), { id, kind, text, details }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 4000);
  }, []);

  const fail = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError) toast(e.message, "error", e.details);
      else toast(e instanceof Error ? e.message : String(e), "error");
    },
    [toast],
  );

  const list = engines.data ?? [];
  const value = useMemo<Lab>(
    () => ({
      engines: list,
      system: system.data,
      metrics: metrics.data,
      offline: Boolean(engines.error && engines.error instanceof ApiError && engines.error.status === 0),
      refreshEngines: engines.refresh,
      toast,
      fail,
      label: (id: string) => list.find((e) => e.id === id)?.label ?? id,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [list, system.data, metrics.data, engines.error, toast, fail],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <div>
              {t.text}
              {t.details.length > 0 && (
                <ul>
                  {t.details.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              )}
            </div>
            <button aria-label="Dismiss" onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
