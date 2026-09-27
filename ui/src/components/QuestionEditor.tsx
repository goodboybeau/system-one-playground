import type { QType } from "../api";
import type { EditorQuestion } from "../lib/request";
import { Seg } from "./common";

const TYPES: Array<{ value: QType; label: string }> = [
  { value: "choice", label: "Choice" },
  { value: "score", label: "Score" },
  { value: "noul", label: "Yes / no" },
];

export function QuestionEditor({
  q,
  onChange,
  onRemove,
  onMove,
  first,
  last,
}: {
  q: EditorQuestion;
  onChange: (q: EditorQuestion) => void;
  onRemove: () => void;
  onMove: (d: -1 | 1) => void;
  first: boolean;
  last: boolean;
}) {
  const set = (patch: Partial<EditorQuestion>) => onChange({ ...q, ...patch });

  return (
    <div className="question" data-question={q.id}>
      <div className="question-head">
        <input className="input sm" aria-label="Question id" value={q.id} onChange={(e) => set({ id: e.target.value })} spellCheck={false} />
        <Seg label="Question type" value={q.type} options={TYPES} onChange={(type) => set({ type })} />
        <span className="grow" />
        <button className="btn ghost icon sm" aria-label="Move question up" disabled={first} onClick={() => onMove(-1)}>
          ↑
        </button>
        <button className="btn ghost icon sm" aria-label="Move question down" disabled={last} onClick={() => onMove(1)}>
          ↓
        </button>
        <button className="btn ghost icon sm" aria-label="Remove question" onClick={onRemove}>
          ✕
        </button>
      </div>
      <div className="question-body">
        <textarea
          className="textarea"
          rows={2}
          aria-label="Instructions"
          placeholder={q.type === "noul" ? "The yes/no statement, e.g. Is the customer asking for a refund?" : "Instructions, e.g. Which team should handle this?"}
          value={q.instructions}
          onChange={(e) => set({ instructions: e.target.value })}
        />
        {q.type === "choice" && <ChoiceOptions q={q} set={set} />}
        {q.type === "score" && <ScoreLevels q={q} set={set} />}
        {q.type === "noul" && (
          <div className="stack" style={{ gap: 6 }}>
            <input className="input" aria-label="What true means" placeholder="Optional: what “yes” means" value={q.trueText} onChange={(e) => set({ trueText: e.target.value })} />
            <input className="input" aria-label="What false means" placeholder="Optional: what “no” means" value={q.falseText} onChange={(e) => set({ falseText: e.target.value })} />
          </div>
        )}
      </div>
    </div>
  );
}

function ChoiceOptions({ q, set }: { q: EditorQuestion; set: (p: Partial<EditorQuestion>) => void }) {
  const update = (i: number, patch: Partial<{ label: string; description: string }>) =>
    set({ options: q.options.map((o, j) => (j === i ? { ...o, ...patch } : o)) });
  return (
    <div className="stack" style={{ gap: 5 }}>
      {q.options.map((o, i) => (
        <div className="opt-row" key={i}>
          <span className="idx">{i + 1}</span>
          <input className="input sm mono" aria-label={`Option ${i + 1} label`} placeholder="label" value={o.label} onChange={(e) => update(i, { label: e.target.value })} spellCheck={false} />
          <input className="input sm" aria-label={`Option ${i + 1} description`} placeholder="description (optional)" value={o.description} onChange={(e) => update(i, { description: e.target.value })} />
          <button className="btn ghost icon sm" aria-label={`Remove option ${i + 1}`} disabled={q.options.length <= 2} onClick={() => set({ options: q.options.filter((_, j) => j !== i) })}>
            ✕
          </button>
        </div>
      ))}
      <div className="row">
        <button className="btn sm" onClick={() => set({ options: [...q.options, { label: "", description: "" }] })}>
          + Option
        </button>
        <span className="hint">
          {q.options.length} options{q.options.length > 20 ? " · Laya's option budget is roughly 20" : ""}
        </span>
      </div>
    </div>
  );
}

function ScoreLevels({ q, set }: { q: EditorQuestion; set: (p: Partial<EditorQuestion>) => void }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      {q.levels.map((l, i) => (
        <div className="opt-row" key={i} style={{ gridTemplateColumns: "22px 1fr 28px" }}>
          <span className="idx">{i}</span>
          <input
            className="input sm"
            aria-label={`Level ${i}`}
            placeholder={i === 0 ? "lowest level" : i === q.levels.length - 1 ? "highest level" : "level"}
            value={l}
            onChange={(e) => set({ levels: q.levels.map((x, j) => (j === i ? e.target.value : x)) })}
          />
          <button className="btn ghost icon sm" aria-label={`Remove level ${i}`} disabled={q.levels.length <= 2} onClick={() => set({ levels: q.levels.filter((_, j) => j !== i) })}>
            ✕
          </button>
        </div>
      ))}
      <div className="row">
        <button className="btn sm" disabled={q.levels.length >= 10} onClick={() => set({ levels: [...q.levels, ""] })}>
          + Level
        </button>
        <span className="hint">Ordered low → high · 2–10 levels</span>
      </div>
    </div>
  );
}
