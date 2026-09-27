import { useEffect, useRef, useState } from "react";

import { api, type JobSnapshot } from "../api";
import { useLab } from "../state";

/**
 * Tracks the job of one kind: the one this page started, or one already running when the
 * page opens (so leaving and coming back keeps showing progress). Polls while it runs.
 */
export function useJob(kind: JobSnapshot["kind"]) {
  const { system, fail, toast } = useLab();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const id = useRef<string | null>(null);

  const active = system?.active_job;
  useEffect(() => {
    if (active && active.kind === kind && id.current !== active.id) {
      id.current = active.id;
      setSnapshot(active);
    }
  }, [active, kind]);

  const running = snapshot?.status === "running";
  useEffect(() => {
    if (!running || !id.current) return;
    const jobId = id.current;
    const t = window.setInterval(async () => {
      try {
        const s = await api.job(jobId);
        if (id.current !== jobId) return;
        setSnapshot(s);
        if (s.status === "done") toast(`${s.title} finished`);
        if (s.status === "error") toast(`${s.title} failed: ${s.error}`, "error");
      } catch (e) {
        fail(e);
      }
    }, 700);
    return () => window.clearInterval(t);
  }, [running, fail, toast]);

  return {
    snapshot,
    track: (s: JobSnapshot) => {
      id.current = s.id;
      setSnapshot(s);
    },
    cancel: async () => {
      if (!id.current) return;
      try {
        await api.cancel(id.current);
      } catch (e) {
        fail(e);
      }
    },
  };
}
