import { useCallback, useEffect, useRef, useState } from "react";

/** Calls `fn` now and every `ms` while mounted; skips a tick if the previous call is still running. */
export function usePoll<T>(fn: () => Promise<T>, ms: number, deps: unknown[] = []): { data: T | null; error: Error | null; refresh: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const busy = useRef(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const tick = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    void tick();
    const id = window.setInterval(() => void tick(), ms);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, tick, ...deps]);

  return { data, error, refresh: () => void tick() };
}

export function useStored<T>(key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage full or disabled: keep working in memory */
    }
  }, [key, value]);
  return [value, setValue];
}

export function useHashRoute(): [string, (r: string) => void] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("?")[0] || "playground";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [route, (r: string) => (window.location.hash = `/${r}`)];
}
