/**
 * Colour follows the engine, never its position in a selection. The eight categorical
 * slots of the reference palette go to the local models; Laya typed-decisions shares
 * Laya's blue at a darker step (it is the same architecture). Jev, the hosted
 * reference, is primary ink; the word-overlap floor is muted grey. Every chart also
 * names engines in text, so colour never carries identity alone.
 */
const SLOTS: Record<string, string> = {
  "laya-en": "--series-1",
  "decider-4b": "--series-2",
  "kev-4b": "--series-3",
  "decider-2b": "--series-4",
  "laya-multi": "--series-5",
  "kev-0.8b": "--series-6",
  "qwen-4b-plain": "--series-7",
  "decider-0.8b": "--series-8",
  "laya-typed": "--series-1-deep",
  jev: "--ink",
  overlap: "--series-muted",
  "gpu-sys": "--series-7",
  "cpu-sys": "--series-muted",
};

export function engineVar(id: string): string {
  return SLOTS[id] ?? "--series-muted";
}

export function engineColor(id: string): string {
  return `var(${engineVar(id)})`;
}
