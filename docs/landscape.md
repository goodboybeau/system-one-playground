# Jev, Laya and the System One landscape

Research notes from 2026-09-26, when the category was about ten days old. Numbers from vendors and blogs are quoted as reported; the independent sources are the Decision Index and this project's own measurements (at the end).

## What the category is

A "System One model" doesn't generate text. You send it `state` (string / JSON / array) plus a map of
typed `questions`, and in one forward pass it returns calibrated probabilities over options **you** defined.
Three primitives, the same across every implementation:

| type | you give | you get back |
|---|---|---|
| `choice` | `criteria`: `{label: description}` or `[labels]` | `choice`, `probabilities{}`, `confidence` |
| `score` | `criteria`: ordered list of level descriptions | `score` (expected level, float), `probabilities`, `confidence` |
| `noul` | `instructions` (optional true/false descriptions) | `noul` = P(true), `confidence` |

Wire contract (TypeSafe, and copied by most open impls): `POST /v1/systemone`
`{ model?, state, questions: { name: { type, instructions, criteria } } }` →
`{ answers: { name: {...} }, usage: { input_tokens, output_tokens: 0 } }`.

## Jev (TypeSafe AI) — closed, hosted

- Launched 2026-09-15; GA 2026-09-21 (waitlist removed, $5 free credit ≈ 120M tokens). Current: `jev-1.13.0` (`jev-latest`, `jev-preview` aliases).
- Founders include Diogo Almeida (ex-OpenAI RLHF / InstructGPT). $40M seed (DCVC).
- Trained on synthetic data with "RLCD" (RL for Calibrated Decisions — proper scoring rules as reward). No paper, no weights, architecture undisclosed.
- API: `POST https://api.typesafe.ai/v1/systemone`; Python + JS SDKs; also on OpenRouter (`typesafe/jev-1.13`) and LiteLLM pass-through.
- Limits: 64k total / 32k state; up to 255 choice options; text only; English-first (other langs work, less reliable).
- Price: **$0.042 / 1M input tokens, output free**. Rate limits 1,200 req/min, 250k tok/s.
- Latency: vendor says 70–500 ms; Decision Index measured 524 ms median over HTTPS.
- Vendor claims "193.6× faster, 444.6× cheaper" — measured on their own 4 workflows vs. big reasoning LLMs. Treat as marketing.
- No customer fine-tuning; you customize via instructions/criteria only.

## Laya (Convai Innovations) — open, Apache-2.0

- Encoder + decision head (no decoder). Each option gets a `[MASK]` marker; one bidirectional pass scores all options.
- Checkpoints (HF `convaiinnovations/laya`, subfolders / sibling repos):

  | ckpt | backbone | params | ctx | notes |
  |---|---|---|---|---|
  | `english` (root) | ModernBERT-large | 421M | 512 | default |
  | `multilingual` | mmBERT-base | 322M | 1024 (up to 8192) | 100+ langs, ~2× faster |
  | `typed-decisions` | ModernBERT-large | 421M | 1024 | fine-tuned on the typed-decisions train split |

- `pip install laya` (Py ≥3.10). `Router(preload=True)` auto-routes by language (<0.5 ms). Extras: `[serve]` (Jev-compatible `laya-serve` on :8000), `[mcp]`, `[onnx]`, `[langchain]`.
- Node: `@receptron/laya` (ONNX Runtime, ~1.7 GB fp32, ~140 ms/call on Apple silicon CPU).
- Browser: ONNX Runtime Web port (vishalmysore/layaForWeb, WASM; 4-bit build works on WebGPU). MLX port: `laya-mlx` (community).
- Hosted: Laya Studio (`api.laya.studio/v1/systemone`), Swiss GPUs, priced "30% under Jev".
- Latency: T4 ~33–40 ms for 1 question, ~160 ms for 10. M1 Max: ~18 ms for 1 question, ~8 ms per extra (anth.us).
- Repo claims 25.9k GitHub stars / 3.9k HF likes in ~10 days — hype level is very high.

## Other open options worth knowing

| Project | Base | Size | Jev-API compatible | Mac-runnable | Decision Index |
|---|---|---|---|---|---|
| **Decider** (Mapika) | Qwen3.5 | 0.8B / 2B / 4B / 35B-A3B, + 2b-vision | yes (`/v1/systemone` + `/decide`) | yes (MPS, ~133 ms) | 4B: **40.7** @ 12.6 ms; 35B-A3B: 47.1; best calibrated |
| **Decider chat** technique | Gemma-4-31B / Qwen3.6-27B | 27–31B | yes | 32 GB Mac: tight/quantized only | **57.3** (≈ Jev) |
| **Bespoke Nimble 9B** | Qwen3.5-9B + LoRA | 9B | similar | yes (MLX/quant) | 39.6, very well calibrated |
| **Kev** (Jared Palmer) | Qwen + LoRA + pointer head | 0.8/4/9B | yes, TypeSafe SDK works | yes | 9B 38.5, 4B 34.6 |
| **simple-jev** | any HF LLM (logit read-out) | varies | no | yes | 55.7 with Qwen3.8-27B |
| **SemIf** | any open LLM, zero training | varies | no | yes, has WebGPU demo | 25.9 (4B) |
| **Von** | ModernBERT | ~395M | yes | yes | — |
| **NanoJev** | Qwen3-0.6B + heads | 0.6B | no | yes | — |
| **GLiNER 2.5 / GLiClass** | GLi family encoders | 74–576M | no | yes | 4–11 |
| Laya | ModernBERT-large | 421M | yes (`laya-serve`) | yes | **6.0** |

Key observation: on the independent board, score tracks **backbone size**. Everything ≥ 27B clusters at ~50–57 (≈ Jev);
4B models ~35–40; ≤1B ~12–20; all BERT-class encoders (Laya included) sit near chance (4–9). Full table: [decision-index.md](decision-index.md).

## Benchmarks — who says what

- **Artificial Analysis**: TypeSafe marketing references AA, but I can't find a Jev page on artificialanalysis.ai (every model URL I tried 404s, and the leaderboard doesn't mention Jev). AA covers generative LLMs; there's no System-One track yet. I found no AA numbers for Jev or Laya.
- **Decision Index 0.2.1** (HF space `multimodalart/jev-decision-index`, 2026-09-27): 67 open entrants + Jev, 38 benchmarks, chance-corrected. Jev **57.9** (#1, ECE 0.074), Laya **6.0** (#58). Open entrants have 0.76 coverage vs. Jev's 1.0 (unanswered = wrong). That skews against open models; worth reading the methodology before quoting.
- **JevBench v1.3** (534 decisions, via HF blog): Jev composite 74.4 vs Laya 54.4; hard cases 74.1% vs 34.1%.
- **Jevals.com**: Jev statistically tied with best of 6 LLMs on PubMedQA nouls at 1/28 the price; Gemini 3.8 Flash beats it on Banking77 choice; "score" board: nothing clearly beats guessing.
- **Laya's own card**: AG News 0.95, spam 0.99, phishing 0.98, Banking77 0.43, toxicity 0.53, SST-5 score 0.37; zero-shot typed-decisions 0.36 (random 0.318). The headline 0.766 "beats Jev" figure is **after fine-tuning on that benchmark's train split**.
- **anth.us paired study** (600 held-out sentiment items, same 140 labels): Jev 76.8% → 87.0% with feedback layer; Laya 72.2% → 80.2%; **Laya fully fine-tuned on 140 labels: 89.6%** (best), but calibration drifted and 42% of untrained questions flipped.
- **Frontier LLMs as comparison**: TypeSafe says Jev ≈ 68% on its 4-workflow bench, close to "GPT-5.6 Terra"-class mid-tier LLMs, at 40–400× lower cost. Independent boards show Gemini 3.8 Flash matching or beating Jev on some tasks at higher price and latency.

## UIs / playgrounds found

- **Laya HF Space** `convaiinnovations/laya-demo`: official Gradio demo, good for quick pokes.
- **laya-playground** (marcosnovaesq): FastAPI + plain HTML, Jev wire-compatible. 0 stars, 3 commits, very minimal.
- **layaForWeb** (vishalmysore.github.io/layaForWeb): fully in-browser ONNX/WASM, no server.
- **Laya³** (webgpu.bonsai.stream/laya3): WebGPU demo on live HF data.
- **SemIf / OpenJev Verdict**: WebGPU playgrounds.
- **Laya Studio** (laya.studio): hosted dashboard with keys and metering. Not open source.
- TypeSafe docs have demos/cookbooks, but there's no public open playground for Jev.
- Nothing I found does what we want: one schema builder with side-by-side Jev / Laya / Decider, latency, and a calibration view. That's the gap for our UI.

## 🚩 Gnarly stuff

1. **Laya's hype vs. independent results.** "Beats Jev" / "can't hallucinate" headlines rest on a fine-tuned-on-benchmark number. Zero-shot it's near chance on the broad Decision Index (6.0 vs Jev 57.9). It's fine for narrow, easy tasks (spam, phishing, topic) and becomes strong once fine-tuned on your labels.
2. **Silent truncation.** English Laya only gets about 320 usable state tokens after questions. Longer input gets cut with no error.
3. **Confidently wrong out of the box.** Shipped ECE is 0.466; you have to refit temperatures on your own data. `act_probability` is anti-correlated with correctness (AUROC 0.30), so gate on `confidence` instead.
4. **`noul` can say a confident "no" on clearly positive input.** Their workaround is a 2-option `choice`. Don't use `yes`/`no`/`true`/`false` as choice keys either. The multilingual `score` rarely picks the first level (position bias).
5. **Options share one token budget** (192–256 tokens), not Jev's 255 options. Above ~20 options you need `predict_shortlist()`.
6. **"Can't hallucinate" is a type guarantee, not a correctness one.** Every one of these can pick the wrong option confidently.
7. **Jev is a black box that drifts.** Decision Index saw 20 answers change on the same inputs between runs. Pin `jev-1.13.0`, not `jev-latest`.
8. **Ecosystem noise.** Hundreds of "alternatives" in 10 days, lots of SEO/AI-written comparison blogs with contradictory numbers (e.g. Jev ctx listed as 32k in one place, 64k in another; Laya license "not specified" in one). Prefer primary sources: model cards, the Decision Index JSON, TypeSafe docs.
9. **"Laya" name collision.** There's an unrelated EEG LeJEPA model (arXiv 2603.16281) and an unrelated notification app (aayushch/laya).

## Sources

- TypeSafe: https://typesafe.ai/blog/introducing-system-one-models-and-jev · https://docs.typesafe.ai/models · https://openrouter.ai/typesafe/jev-1.13
- Wikipedia: https://en.wikipedia.org/wiki/Jev_(AI_model)
- Laya: https://huggingface.co/convaiinnovations/laya · https://github.com/NandhaKishorM/laya · https://laya.studio/learn/what-is-laya · https://github.com/receptron/laya
- Decider: https://github.com/Mapika/decider · https://www.orcarouter.ai/blog/laya-vs-decider
- Decision Index: https://multimodalart-jev-decision-index.static.hf.space (raw data: `data/index.json` on that Space)
- Jevals: https://jevals.com/
- Jev vs Laya: https://huggingface.co/blog/sora-2/jev-vs-laya-hosted-api-or-open-weights-2026-guide · https://anth.us/blog/jev-vs-laya/
- Alternatives lists: https://www.datacamp.com/blog/top-open-source-jev-alternatives · https://madewithjev.com/open-source-jev · https://github.com/cobanov/awesome-jev
- UIs: https://github.com/marcosnovaesq/laya-playground · https://webgpu.bonsai.stream/laya3/ · https://huggingface.co/spaces/convaiinnovations/laya-demo
- Commentary: https://www.latent.space/p/ainews-jev-a-system-one-model-that

## Local results (M1 Max 32 GB, 2026-09-27)

Measured by the lab (`make suite`): 100 seeded items per dataset, one engine at a time, in the macOS sandbox. Numbers are accuracy with the median round-trip latency beneath. The mean column is the unweighted mean over the nine datasets; it's not the Decision Index.

| Engine | AG News | Bank-10 | Bank-77 | Emotion | MASSIVE | Injection | PubMedQA | Spam | SST-5 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|
| Decider 4B | 91% <br><sub>262 ms</sub> | 89% <br><sub>342 ms</sub> | 89% <br><sub>1002 ms</sub> | 70% <br><sub>190 ms</sub> | 79% <br><sub>415 ms</sub> | 67% <br><sub>177 ms</sub> | 88% <br><sub>637 ms</sub> | 95% <br><sub>245 ms</sub> | 51% <br><sub>527 ms</sub> | **80%** |
| Decider 2B | 91% <br><sub>141 ms</sub> | 90% <br><sub>169 ms</sub> | 84% <br><sub>396 ms</sub> | 78% <br><sub>118 ms</sub> | 79% <br><sub>187 ms</sub> | 60% <br><sub>110 ms</sub> | 84% <br><sub>261 ms</sub> | 95% <br><sub>122 ms</sub> | 56% <br><sub>221 ms</sub> | **80%** |
| Kev 4B | 91% <br><sub>192 ms</sub> | 94% <br><sub>238 ms</sub> | 90% <br><sub>629 ms</sub> | 42% <br><sub>163 ms</sub> | 71% <br><sub>317 ms</sub> | 64% <br><sub>168 ms</sub> | 86% <br><sub>531 ms</sub> | 90% <br><sub>172 ms</sub> | 57% <br><sub>166 ms</sub> | **76%** |
| Decider 0.8B | 94% <br><sub>142 ms</sub> | 93% <br><sub>157 ms</sub> | 80% <br><sub>267 ms</sub> | 72% <br><sub>92 ms</sub> | 63% <br><sub>133 ms</sub> | 61% <br><sub>78 ms</sub> | 78% <br><sub>194 ms</sub> | 95% <br><sub>93 ms</sub> | 47% <br><sub>155 ms</sub> | **76%** |
| Qwen3.5 4B · plain LLM | 91% <br><sub>329 ms</sub> | 82% <br><sub>340 ms</sub> | 66% <br><sub>942 ms</sub> | 51% <br><sub>251 ms</sub> | 65% <br><sub>391 ms</sub> | 71% <br><sub>248 ms</sub> | 86% <br><sub>624 ms</sub> | 93% <br><sub>251 ms</sub> | 45% <br><sub>256 ms</sub> | **72%** |
| Kev 0.8B | 91% <br><sub>44 ms</sub> | 94% <br><sub>51 ms</sub> | 82% <br><sub>124 ms</sub> | 43% <br><sub>39 ms</sub> | 58% <br><sub>64 ms</sub> | 64% <br><sub>38 ms</sub> | 77% <br><sub>101 ms</sub> | 58% <br><sub>40 ms</sub> | 46% <br><sub>39 ms</sub> | **68%** |
| Laya · Typed-decisions | 96% <br><sub>39 ms</sub> | 76% <br><sub>43 ms</sub> | 35% <br><sub>65 ms</sub> | 42% <br><sub>29 ms</sub> | 35% <br><sub>44 ms</sub> | 72% <br><sub>32 ms</sub> | 53% <br><sub>68 ms</sub> | 85% <br><sub>33 ms</sub> | 43% <br><sub>32 ms</sub> | **60%** |
| Laya · English | 96% <br><sub>38 ms</sub> | 76% <br><sub>41 ms</sub> | 38% <br><sub>64 ms</sub> | 41% <br><sub>28 ms</sub> | 26% <br><sub>44 ms</sub> | 78% <br><sub>31 ms</sub> | 52% <br><sub>66 ms</sub> | 97% <br><sub>33 ms</sub> | 32% <br><sub>31 ms</sub> | **60%** |
| Laya · Multilingual | 92% <br><sub>24 ms</sub> | 71% <br><sub>23 ms</sub> | 35% <br><sub>34 ms</sub> | 36% <br><sub>19 ms</sub> | 46% <br><sub>24 ms</sub> | 69% <br><sub>20 ms</sub> | 55% <br><sub>36 ms</sub> | 85% <br><sub>21 ms</sub> | 30% <br><sub>24 ms</sub> | **58%** |
| Word-overlap baseline | 40% <br><sub>0.9 ms</sub> | 55% <br><sub>1.0 ms</sub> | 41% <br><sub>1.2 ms</sub> | 16% <br><sub>0.9 ms</sub> | 9% <br><sub>1.0 ms</sub> | 76% <br><sub>0.9 ms</sub> | 50% <br><sub>1.0 ms</sub> | 51% <br><sub>0.9 ms</sub> | 18% <br><sub>0.9 ms</sub> | **40%** |

What the numbers say:

- **Kev and Decider win on quality.** At 0.8–4B they lead on every hard dataset (Banking77, MASSIVE, PubMedQA, SST-5). Kev 0.8B on MLX gets 82% on Banking77 at 124 ms; Laya gets 35–38%.
- **Laya is fast and narrow.** It's excellent on easy tasks (96% AG News, 97% spam) at 20–65 ms and 2–3 GB. It's near chance on fine-grained or long-input tasks, and on Banking77 **the word-overlap baseline beats it** (41% vs 38%).
- **Decision training matters.** The stock Qwen3.5-4B read as a plain LLM trails the same-size decision models on Banking77 (66% vs 89–90%) and on calibration.
- **Bigger isn't always better.** Decider 2B ties or beats Decider 4B on 6 of 9 datasets at about half the latency. Emotion confuses every model (joy vs love).
- **Guardrails are hard for all of them.** The best score on prompt injections is 78% (Laya English); the word-overlap baseline gets 76%.
- **Memory:** Laya 2–3.3 GB, 0.8B models about 3 GB, 2B about 6 GB, 4B 10–13 GB, and Kev 4B peaks near 17 GB while loading.
- **Not comparable to Jev yet.** There's no API key; with one, the same suite adds Jev as a row.
- **Anomaly worth a look:** Kev 0.8B scores 58% on SMS spam, while every other model scores 85%+. Open *Benchmarks → SMS spam · 100 → Items* to see the split decisions.
