const GB = 1024 ** 3;
const MB = 1024 ** 2;

/** Binary units, labelled the way macOS labels them (a 32 GB Mac shows 32 GB, not 34.4). */
export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  if (n >= GB) return `${(n / GB).toFixed(n >= 10 * GB ? 1 : 2)} GB`;
  if (n >= MB) return `${(n / MB).toFixed(0)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}

/** Axis ticks for byte scales: whole GB (or MB) steps. */
export function byteTicks(max: number): number[] {
  const unit = max >= 2 * GB ? GB : MB;
  const raw = max / unit / 4;
  const step = [1, 2, 5, 10, 20, 50, 100, 200, 500].find((s) => s >= raw) ?? 1000;
  const top = Math.max(step, Math.ceil(max / unit / step) * step);
  return Array.from({ length: top / step + 1 }, (_, i) => i * step * unit);
}

export function clock(t: number): string {
  return new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function ms(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  if (n === 0) return "0 ms";
  if (n >= 10_000) return `${(n / 1000).toFixed(1)} s`;
  if (n >= 1000) return `${(n / 1000).toFixed(2)} s`;
  if (n >= 100) return `${n.toFixed(0)} ms`;
  if (n >= 10) return `${n.toFixed(1)} ms`;
  return `${n.toFixed(2)} ms`;
}

export function secs(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : ms(n * 1000);
}

export function pct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function num(n: number | null | undefined, digits = 3): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

export function params(n: number): string {
  if (!n) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  return `${Math.round(n / 1e6)}M`;
}

export function cpu(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `${n.toFixed(0)}%`;
}

export function ago(t: number): string {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(t * 1000).toLocaleDateString();
}

export function preview(state: unknown, max = 140): string {
  const s = typeof state === "string" ? state : JSON.stringify(state);
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}
