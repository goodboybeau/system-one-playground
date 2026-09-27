import { type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { engineColor } from "../lib/colors";
import { clock } from "../lib/format";

const AXIS = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 11 }, tickLine: false };
const GRID = <CartesianGrid stroke="var(--grid)" strokeDasharray="0" vertical={false} />;

export type Series = { id: string; label: string };

export function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  return (
    <div className="legend">
      {series.map((s) => (
        <span key={s.id}>
          <i className="swatch" style={{ background: engineColor(s.id) }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

export function ChartCard({ title, sub, children, legend }: { title: string; sub?: string; children: ReactNode; legend?: Series[] }) {
  return (
    <div className="card chart-card">
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <p>{sub}</p>}
        </div>
      </div>
      <div className="chart-body">{children}</div>
      {legend && <Legend series={legend} />}
    </div>
  );
}

type TipPayload = { dataKey?: string | number; value?: number | null; color?: string; name?: string };

function TimeTip({
  active,
  payload,
  label,
  fmt,
  names,
}: {
  active?: boolean;
  payload?: TipPayload[];
  label?: number;
  fmt: (v: number) => string;
  names: Record<string, string>;
}) {
  if (!active || !payload?.length || label === undefined) return null;
  const rows = payload.filter((p) => p.value !== null && p.value !== undefined);
  return (
    <div className="tooltip">
      <div className="t-head">{clock(label)}</div>
      {rows.map((p) => (
        <div className="t-row" key={String(p.dataKey)}>
          <span>
            <i className="swatch" style={{ background: engineColor(String(p.dataKey)) }} />
            {names[String(p.dataKey)] ?? p.dataKey}
          </span>
          <span>{fmt(p.value as number)}</span>
        </div>
      ))}
    </div>
  );
}

/** One measure over time, one line per engine. Timestamps are merged onto a shared axis. */
export function TimeLines({
  data,
  series,
  fmt,
  domain,
  ticks,
  height = 200,
}: {
  data: Array<Record<string, number | null>>;
  series: Series[];
  fmt: (v: number) => string;
  domain?: [number, number | "auto"];
  ticks?: number[];
  height?: number;
}) {
  const names = Object.fromEntries(series.map((s) => [s.id, s.label]));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        {GRID}
        <XAxis
          dataKey="t"
          type="number"
          domain={["dataMin", "dataMax"]}
          tickFormatter={clock}
          minTickGap={48}
          {...AXIS}
        />
        <YAxis tickFormatter={fmt} width={64} domain={ticks ? [0, ticks[ticks.length - 1]!] : (domain ?? [0, "auto"])} ticks={ticks} {...AXIS} />
        <Tooltip content={<TimeTip fmt={fmt} names={names} />} cursor={{ stroke: "var(--axis)" }} isAnimationActive={false} />
        {series.map((s) => (
          <Line
            key={s.id}
            dataKey={s.id}
            stroke={engineColor(s.id)}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
            isAnimationActive={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function BarTip({ active, payload, fmt }: { active?: boolean; payload?: Array<{ payload: { label: string; id: string; value: number; extra?: string } }>; fmt: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]!.payload;
  return (
    <div className="tooltip">
      <div className="t-head">{d.label}</div>
      <div className="t-row">
        <span>value</span>
        <span>{fmt(d.value)}</span>
      </div>
      {d.extra && <div className="t-row">{d.extra}</div>}
    </div>
  );
}

/** Horizontal bars, one per engine, labelled on the axis so colour never carries identity alone. */
export function EngineBars({
  rows,
  fmt,
  domain,
  reference,
}: {
  rows: Array<{ id: string; label: string; value: number; extra?: string }>;
  fmt: (v: number) => string;
  domain?: [number, number | "auto"];
  reference?: { value: number; label: string };
}) {
  const height = Math.max(90, rows.length * 34 + 30);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, bottom: 0, left: 4 }} barCategoryGap={8}>
        <CartesianGrid stroke="var(--grid)" horizontal={false} />
        <XAxis type="number" tickFormatter={fmt} domain={domain ?? [0, "auto"]} {...AXIS} />
        <YAxis type="category" dataKey="label" width={170} {...AXIS} tick={{ fill: "var(--ink-2)", fontSize: 12 }} />
        <Tooltip content={<BarTip fmt={fmt} />} cursor={{ fill: "var(--surface-2)" }} isAnimationActive={false} />
        {reference && (
          <ReferenceLine x={reference.value} stroke="var(--muted)" strokeDasharray="4 3" label={{ value: reference.label, fill: "var(--muted)", fontSize: 11, position: "top" }} />
        )}
        <Bar
          dataKey="value"
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
          label={{ position: "right", formatter: (v: unknown) => fmt(Number(v)), fill: "var(--ink-2)", fontSize: 11.5 }}
          shape={(props: unknown) => {
            const p = props as { x: number; y: number; width: number; height: number; payload: { id: string } };
            const w = Math.max(0, p.width);
            const r = Math.min(4, w / 2, p.height / 2);
            return (
              <path
                d={`M${p.x},${p.y} h${w - r} a${r},${r} 0 0 1 ${r},${r} v${p.height - 2 * r} a${r},${r} 0 0 1 -${r},${r} h-${w - r} z`}
                fill={engineColor(p.payload.id)}
              />
            );
          }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

function XYTip({
  active,
  payload,
  label,
  fmt,
  xLabel,
  names,
}: {
  active?: boolean;
  payload?: TipPayload[];
  label?: number | string;
  fmt: (v: number) => string;
  xLabel: (x: number | string) => string;
  names: Record<string, string>;
}) {
  if (!active || !payload?.length || label === undefined) return null;
  return (
    <div className="tooltip">
      <div className="t-head">{xLabel(label)}</div>
      {payload
        .filter((p) => p.value !== null && p.value !== undefined)
        .map((p) => (
          <div className="t-row" key={String(p.dataKey)}>
            <span>
              <i className="swatch" style={{ background: p.color }} />
              {names[String(p.dataKey)] ?? p.name ?? p.dataKey}
            </span>
            <span>{fmt(p.value as number)}</span>
          </div>
        ))}
    </div>
  );
}

/** Lines over a numeric x (confidence bin, concurrency). `lines` carry their own colour. */
export function XYLines({
  data,
  x,
  lines,
  fmt,
  xFmt,
  xLabel,
  yDomain,
  xDomain,
  diagonal,
  height = 240,
  xTicks,
}: {
  data: Array<Record<string, number | null>>;
  x: string;
  lines: Array<{ key: string; label: string; color: string; dash?: string }>;
  fmt: (v: number) => string;
  xFmt: (v: number) => string;
  xLabel: (v: number | string) => string;
  yDomain?: [number, number | "auto"];
  xDomain?: [number | "dataMin", number | "dataMax"];
  diagonal?: boolean;
  height?: number;
  xTicks?: number[];
}) {
  const names = Object.fromEntries(lines.map((l) => [l.key, l.label]));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 14, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid)" />
        <XAxis dataKey={x} type="number" domain={xDomain ?? ["dataMin", "dataMax"]} tickFormatter={xFmt} ticks={xTicks} {...AXIS} />
        <YAxis tickFormatter={fmt} width={56} domain={yDomain ?? [0, "auto"]} {...AXIS} />
        <Tooltip content={<XYTip fmt={fmt} xLabel={xLabel} names={names} />} isAnimationActive={false} cursor={{ stroke: "var(--axis)" }} />
        {diagonal && (
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 },
            ]}
            stroke="var(--muted)"
            strokeDasharray="4 3"
            ifOverflow="extendDomain"
          />
        )}
        {lines.map((l) => (
          <Line
            key={l.key}
            dataKey={l.key}
            name={l.label}
            stroke={l.color}
            strokeWidth={2}
            strokeDasharray={l.dash}
            dot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface)", fill: l.color }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }}
            isAnimationActive={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Tiny inline trend for engine cards. */
export function Sparkline({ values, color, max }: { values: number[]; color: string; max?: number }) {
  const w = 120;
  const h = 26;
  if (values.length < 2) return <svg width={w} height={h} aria-hidden />;
  const top = Math.max(max ?? 0, ...values, 1e-9);
  const step = w / (values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - (v / top) * (h - 4)).toFixed(1)}`);
  return (
    <svg width={w} height={h} aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

/** Confusion matrix as a one-hue sequential heatmap. Rows are gold labels, columns predictions. */
export function Confusion({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const n = labels.length;
  const max = Math.max(1, ...matrix.flat());
  const steps = ["--seq-0", "--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5"];
  const color = (v: number) => (v === 0 ? "var(--surface-2)" : `var(${steps[Math.min(5, 1 + Math.floor((v / max) * 4.999))]})`);
  const ink = (v: number) => (v / max > 0.55 ? "var(--heat-ink-strong)" : "var(--ink-2)");
  const short = (s: string) => (s.length > 14 ? `${s.slice(0, 13)}…` : s);
  const cols = `minmax(90px, 140px) repeat(${n}, minmax(0, 1fr))`;
  if (n > 20) {
    return <p className="muted small">{n} labels is too many to draw as a matrix; see the item table below.</p>;
  }
  return (
    <div>
      <div className="heat" style={{ gridTemplateColumns: cols, maxWidth: 140 + n * 52 }}>
        <span />
        {labels.map((l) => (
          <span key={l} className="axis" title={l} style={{ textAlign: "center" }}>
            {short(l)}
          </span>
        ))}
        {matrix.map((row, i) => [
          <span key={`l${i}`} className="axis" title={labels[i]}>
            {short(labels[i]!)}
          </span>,
          ...row.map((v, j) => (
            <span
              key={`${i}-${j}`}
              className="cell"
              title={`gold ${labels[i]} → predicted ${labels[j]}: ${v}`}
              style={{ background: color(v), color: ink(v), outline: i === j ? "1px solid var(--axis)" : undefined }}
            >
              {v || ""}
            </span>
          )),
        ])}
      </div>
      <p className="muted small" style={{ margin: "8px 0 0" }}>
        Rows: correct answer. Columns: what the engine chose. The diagonal is right.
      </p>
    </div>
  );
}
