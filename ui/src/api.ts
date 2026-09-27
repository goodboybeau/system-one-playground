export type QType = "choice" | "score" | "noul";

export type WireQuestion = {
  type: QType;
  instructions?: unknown;
  criteria?: unknown;
};

export type WireRequest = {
  state: unknown;
  questions: Record<string, WireQuestion>;
};

export type ChoiceAnswer = {
  type: "choice";
  choice: string;
  probabilities: Record<string, number>;
  confidence: number;
  p_top: number;
};
export type ScoreAnswer = {
  type: "score";
  score: number;
  level: number;
  probabilities: Record<string, number>;
  legend: Record<string, string>;
  confidence: number;
  p_top: number;
};
export type NoulAnswer = { type: "noul"; noul: number; confidence: number; p_top: number };
export type Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer;

export type Stats = {
  n: number;
  mean: number | null;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  min: number | null;
  max: number | null;
};

export type ColdStart = { process_s: number | null; load_s: number | null; warmup_ms: number | null; total_s: number | null };

export type EngineRun = {
  id: string;
  device: string;
  threads: number | null;
  port: number;
  pid: number;
  status: "starting" | "loading" | "warming" | "ready" | "error" | "exited" | "stopping" | "stopped";
  error: string | null;
  spawned_at: number;
  ready_at: number | null;
  cold_start: ColdStart;
  info: Record<string, unknown>;
  requests: number;
  cpu_percent: number | null;
  footprint: number | null;
  rss: number | null;
  threads_os: number | null;
  peak_footprint: number;
};

export type Engine = {
  id: string;
  label: string;
  model: string;
  devices: string[];
  params: number;
  architecture: string;
  license: string;
  source: string;
  note: string;
  remote: boolean;
  installed: boolean;
  missing_secrets: string[];
  missing_weights: string[];
  weights_bytes: number | null;
  memory_needed: Record<string, number>;
  run: EngineRun | null;
  cold_starts: Array<{ device: string; t: number; total_s: number | null; load_s: number | null; warmup_ms: number | null }>;
};

export type SystemInfo = {
  chip: string;
  cores: number;
  physical_cores: number;
  memory_total: number;
  memory_available: number;
  macos: string;
  python: string;
  sandbox: boolean;
  active_job: JobSnapshot | null;
};

export type ProcSample = { t: number; cpu_percent: number; cpu_seconds: number; footprint: number; rss: number; threads: number };
export type SystemSample = {
  t: number;
  cpu_percent: number;
  memory_used: number;
  memory_total: number;
  gpu_percent: number | null;
  gpu_memory: number | null;
};
export type Metrics = {
  now: number;
  system: SystemSample[];
  engines: Record<string, { status: string; samples: ProcSample[] }>;
};

export type CallResult = {
  engine: string;
  status: number;
  wall_ms: number;
  cpu_ms?: number | null;
  error?: string;
  details?: string[];
  answers?: Record<string, Answer>;
  usage?: { input_tokens: number | null; output_tokens: number };
  timing?: { infer_ms: number; queue_ms: number };
  warnings?: string[];
  raw_answers?: unknown;
  repeat?: { n: number; ok: number; wall: Stats; infer: Stats; cpu: Stats };
  footprint?: number | null;
  device?: string | null;
};

export type CompareResponse = { mode: string; elapsed_ms: number; results: CallResult[] };

export type Dataset = {
  name: string;
  title: string;
  task: QType;
  labels?: string[];
  legend?: string[];
  source: string;
  description: string;
  items: number;
};

export type Preset = { id: string; title: string; description: string; tags?: string[]; request: WireRequest };

export type Reliability = { lo: number; hi: number; n: number; confidence: number | null; accuracy: number | null };

export type Summary = {
  items: number;
  answered: number;
  coverage: number;
  accuracy: number;
  accuracy_answered: number | null;
  ece: number | null;
  brier: number | null;
  wrong_at_95: number | null;
  auto_at_95: number;
  mean_p_top: number | null;
  reliability: Reliability[];
  mae?: number;
  confusion?: { labels: string[]; matrix: number[][] };
};

export type Resources = { samples: number; cpu_avg?: number; cpu_peak?: number; footprint_peak?: number; footprint_start?: number };

export type BenchAnswer = {
  wall_ms: number;
  error?: string;
  predicted?: string;
  correct?: boolean;
  p_top?: number;
  top?: Array<[string, number]>;
  warnings?: string[];
  noul?: number;
  score?: number;
};

export type BenchEngine = {
  error?: string;
  device?: string;
  info?: Record<string, unknown>;
  answers?: BenchAnswer[];
  summary?: Summary;
  by_lang?: Record<string, number> | null;
  latency?: { wall: Stats; infer: Stats };
  cpu_ms?: Stats;
  errors?: Record<string, number>;
  truncated?: number;
  elapsed_s?: number;
  resources?: Resources;
};

export type BenchResult = {
  dataset: Dataset;
  items: Array<{ id: string; gold: unknown; lang: string | null; state: unknown }>;
  engines: Record<string, BenchEngine>;
  error?: string | null;
};

export type OverviewSlice = {
  dataset: string;
  limit: number;
  title: string;
  task: QType | null;
  engines: Record<string, { accuracy: number; ece: number | null; auto_at_95: number; p50: number | null; at: number }>;
};

export type Report = BenchResult & { runs: string[] };

export type LoadLevel = {
  concurrency: number;
  requests: number;
  ok: number;
  errors: number;
  elapsed_s: number;
  throughput_rps: number | null;
  latency: Stats;
  queue: Stats;
  resources: Resources;
};

export type LoadResult = { engine: string; device: string; levels: LoadLevel[]; error?: string | null };

export type JobSnapshot = {
  id: string;
  kind: "bench" | "loadtest";
  title: string;
  config: Record<string, unknown>;
  status: "running" | "done" | "cancelled" | "error";
  created: number;
  finished: number | null;
  progress: { done: number; total: number; engine: string | null };
  error: string | null;
  result?: BenchResult | LoadResult;
};

export type RunRow = {
  id: string;
  kind: "bench" | "loadtest";
  title: string;
  created: number;
  finished: number | null;
  status: string;
  config: Record<string, unknown>;
  result?: BenchResult | LoadResult | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details: string[] = [],
  ) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the lab gateway. Is `make lab` running?");
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, `Unexpected response (${res.status})`);
  }
  if (!res.ok) {
    const d = (data ?? {}) as { error?: string; details?: string[] };
    throw new ApiError(res.status, d.error ?? `Request failed (${res.status})`, d.details ?? []);
  }
  return data as T;
}

export const api = {
  system: () => call<SystemInfo>("GET", "/api/system"),
  engines: () => call<Engine[]>("GET", "/api/engines"),
  start: (id: string, body: { device?: string; threads?: number | null; force?: boolean }) =>
    call<EngineRun>("POST", `/api/engines/${id}/start`, body),
  stop: (id: string) => call<{ stopped: string }>("POST", `/api/engines/${id}/stop`),
  log: (id: string) => call<{ log: string }>("GET", `/api/engines/${id}/log?lines=300`),
  compare: (body: { request: WireRequest; engines: string[]; repeat: number; mode: "sequential" | "parallel" }) =>
    call<CompareResponse>("POST", "/api/compare", body),
  metrics: (since: number) => call<Metrics>("GET", `/api/metrics?since=${since}`),
  datasets: () => call<Dataset[]>("GET", "/api/datasets"),
  presets: () => call<Preset[]>("GET", "/api/presets"),
  bench: (body: { dataset: string; engines: string[]; limit: number | null }) => call<JobSnapshot>("POST", "/api/bench", body),
  loadtest: (body: { engine: string; request: WireRequest; levels: number[]; per_level: number }) =>
    call<JobSnapshot>("POST", "/api/loadtest", body),
  job: (id: string) => call<JobSnapshot>("GET", `/api/jobs/${id}`),
  cancel: (id: string) => call<JobSnapshot>("POST", `/api/jobs/${id}/cancel`),
  runs: () => call<RunRow[]>("GET", "/api/runs"),
  report: (dataset: string, limit: number) => call<Report>("GET", `/api/report?dataset=${encodeURIComponent(dataset)}&limit=${limit}`),
  overview: () => call<{ slices: OverviewSlice[] }>("GET", "/api/report/overview"),
  run: (id: string) => call<RunRow>("GET", `/api/runs/${id}`),
  deleteRun: (id: string) => call<{ deleted: string }>("DELETE", `/api/runs/${id}`),
};
