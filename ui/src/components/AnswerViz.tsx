import type { Answer, WireQuestion } from "../api";
import { engineColor } from "../lib/colors";

const MAX_ROWS = 8;

export function verdict(a: Answer): string {
  if (a.type === "choice") return a.choice;
  if (a.type === "score") return `${a.legend[String(a.level)] ?? a.level}`;
  return a.noul >= 0.5 ? "yes" : "no";
}

/** A comparable key for agreement: the chosen option, the modal level, or the yes/no side. */
export function decisionKey(a: Answer): string {
  if (a.type === "choice") return a.choice;
  if (a.type === "score") return String(a.level);
  return a.noul >= 0.5 ? "yes" : "no";
}

export function AnswerViz({ answer, engine, question }: { answer: Answer; engine: string; question: WireQuestion }) {
  const color = engineColor(engine);
  if (answer.type === "noul") {
    return (
      <div>
        <div className="gauge" aria-label={`Probability yes ${(answer.noul * 100).toFixed(1)}%`}>
          <div className="fill" style={{ width: `${answer.noul * 100}%`, background: color }} />
          <div className="mid" />
        </div>
        <div className="row spread small muted" style={{ marginTop: 3 }}>
          <span>no</span>
          <span className="num ink-2">P(yes) {(answer.noul * 100).toFixed(1)}%</span>
          <span>yes</span>
        </div>
      </div>
    );
  }
  if (answer.type === "score") {
    const n = Object.keys(answer.probabilities).length;
    const cols = `repeat(${n}, minmax(0, 1fr))`;
    return (
      <div>
        <div className="levels" style={{ gridTemplateColumns: cols }}>
          {Array.from({ length: n }, (_, i) => {
            const p = answer.probabilities[String(i)] ?? 0;
            return (
              <div className="lv" key={i} title={`${answer.legend[String(i)]}: ${(p * 100).toFixed(1)}%`}>
                <span style={{ height: `${Math.max(2, p * 100)}%`, background: color, opacity: i === answer.level ? 1 : 0.45 }} />
              </div>
            );
          })}
        </div>
        <div className="level-labels" style={{ gridTemplateColumns: cols }}>
          {Array.from({ length: n }, (_, i) => (
            <span key={i} title={answer.legend[String(i)]} style={{ fontWeight: i === answer.level ? 650 : 400, color: i === answer.level ? "var(--ink)" : undefined }}>
              {answer.legend[String(i)]}
            </span>
          ))}
        </div>
        <div className="small muted num" style={{ marginTop: 4 }}>
          expected level {answer.score.toFixed(2)} of {n - 1}
        </div>
      </div>
    );
  }
  const labels = Object.keys(answer.probabilities);
  const sorted = labels.length > MAX_ROWS ? [...labels].sort((a, b) => answer.probabilities[b]! - answer.probabilities[a]!) : labels;
  const shown = sorted.slice(0, MAX_ROWS);
  const hidden = labels.length - shown.length;
  const descriptions = (question.criteria && !Array.isArray(question.criteria) ? question.criteria : {}) as Record<string, unknown>;
  return (
    <div className="probs">
      {shown.map((l) => {
        const p = answer.probabilities[l]!;
        const d = descriptions[l];
        return (
          <div className={`prob-row${l === answer.choice ? " top" : ""}`} key={l} title={typeof d === "string" ? d : undefined}>
            <span className="lbl">{l}</span>
            <div className="prob-track">
              <div className="prob-fill" style={{ width: `${p * 100}%`, background: color, opacity: l === answer.choice ? 1 : 0.45 }} />
            </div>
            <span className="v">{(p * 100).toFixed(1)}%</span>
          </div>
        );
      })}
      {hidden > 0 && <div className="small muted">+ {hidden} more options, together {(sorted.slice(MAX_ROWS).reduce((s, l) => s + answer.probabilities[l]!, 0) * 100).toFixed(1)}%</div>}
    </div>
  );
}
