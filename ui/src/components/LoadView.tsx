import type { LoadResult } from "../api";
import { engineColor } from "../lib/colors";
import { bytes, cpu, ms, num } from "../lib/format";
import { useLab } from "../state";
import { ChartCard, XYLines } from "./charts";
import { download, EngineName } from "./common";

export function LoadView({ result }: { result: LoadResult }) {
  const { label } = useLab();
  const levels = result.levels;
  if (!levels.length) return null;
  const color = engineColor(result.engine);
  const peak = levels.reduce((a, b) => ((b.throughput_rps ?? 0) > (a.throughput_rps ?? 0) ? b : a));
  const single = levels[0]!;
  const rows = levels.map((l) => ({ c: l.concurrency, rps: l.throughput_rps, p50: l.latency.p50, p95: l.latency.p95, p99: l.latency.p99 }));
  const ticks = levels.map((l) => l.concurrency);

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="kpis">
        <div className="card kpi">
          <span>Engine</span>
          <strong style={{ fontSize: 15 }}>
            <EngineName id={result.engine} label={label(result.engine)} />
          </strong>
          <small>{result.device}</small>
        </div>
        <div className="card kpi">
          <span>Peak throughput</span>
          <strong>{num(peak.throughput_rps, 1)} req/s</strong>
          <small>at {peak.concurrency} concurrent</small>
        </div>
        <div className="card kpi">
          <span>Latency, one at a time</span>
          <strong>{ms(single.latency.p50)}</strong>
          <small>p95 {ms(single.latency.p95)}</small>
        </div>
        <div className="card kpi">
          <span>Peak memory</span>
          <strong>{bytes(Math.max(...levels.map((l) => l.resources.footprint_peak ?? 0)))}</strong>
          <small>physical footprint</small>
        </div>
      </div>

      <div className="chart-grid">
        <ChartCard title="Throughput" sub="Successful requests per second at each concurrency level">
          <XYLines
            data={rows}
            x="c"
            lines={[{ key: "rps", label: "req/s", color }]}
            fmt={(v) => `${v.toFixed(1)}/s`}
            xFmt={(v) => String(v)}
            xLabel={(v) => `${v} concurrent`}
            xTicks={ticks}
            xDomain={["dataMin", "dataMax"]}
          />
        </ChartCard>
        <ChartCard title="Latency" sub="Round trip. Engines answer one request at a time, so extra concurrency becomes queueing.">
          <XYLines
            data={rows}
            x="c"
            lines={[
              { key: "p50", label: "p50", color },
              { key: "p95", label: "p95", color, dash: "6 4" },
              { key: "p99", label: "p99", color, dash: "2 3" },
            ]}
            fmt={ms}
            xFmt={(v) => String(v)}
            xLabel={(v) => `${v} concurrent`}
            xTicks={ticks}
            xDomain={["dataMin", "dataMax"]}
          />
          <div className="legend" style={{ padding: "4px 0 0" }}>
            <span>solid p50</span>
            <span>dashed p95</span>
            <span>dotted p99</span>
          </div>
        </ChartCard>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Levels</h3>
          <button className="btn sm" onClick={() => download(`loadtest-${result.engine}.json`, result)}>
            Export JSON
          </button>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th className="r">Concurrency</th>
                <th className="r">Requests</th>
                <th className="r">Errors</th>
                <th className="r">Throughput</th>
                <th className="r">p50</th>
                <th className="r">p95</th>
                <th className="r">p99</th>
                <th className="r" title="Median time spent waiting for the engine's single worker">Queue p50</th>
                <th className="r">CPU avg</th>
                <th className="r">CPU peak</th>
                <th className="r">Peak mem</th>
              </tr>
            </thead>
            <tbody>
              {levels.map((l) => (
                <tr key={l.concurrency}>
                  <td className="r">{l.concurrency}</td>
                  <td className="r">{l.requests}</td>
                  <td className="r">{l.errors ? <span className="bad-mark">{l.errors}</span> : 0}</td>
                  <td className="r">{num(l.throughput_rps, 1)}/s</td>
                  <td className="r">{ms(l.latency.p50)}</td>
                  <td className="r">{ms(l.latency.p95)}</td>
                  <td className="r">{ms(l.latency.p99)}</td>
                  <td className="r">{ms(l.queue.p50)}</td>
                  <td className="r">{cpu(l.resources.cpu_avg)}</td>
                  <td className="r">{cpu(l.resources.cpu_peak)}</td>
                  <td className="r">{bytes(l.resources.footprint_peak)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
