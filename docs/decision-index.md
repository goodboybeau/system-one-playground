# Decision Index 0.2.1 — full board

Source: https://multimodalart-jev-decision-index.static.hf.space (data/index.json, generated 2026-09-27T02:14:51+00:00). Score = chance-corrected balanced skill (0 = random, 100 = perfect). 38 benchmarks, 1× RTX PRO 6000. ECE / wrong@95 = calibration (lower is better). Latency = median ms, local single process — Jev's is a hosted HTTPS round trip, so not comparable.

| # | Model | Score | Kind | Base | Params (M) | ECE | wrong@95% conf | Median ms | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Jev 1.13 (closed, hosted)** | 57.9 | hosted | ? | ? | 0.074 | 2.1% | 524.1 | 1.00 |
| 2 | Surogate Rune 26B-A4B v3 (bf16) | 57.4 | full fine-tune | google/gemma-4-26B-A4B-it | 25806 | 0.120 | 4.8% | 120.5 | 0.76 |
| 3 | Decider chat · Gemma-4-31B | 57.3 | inference technique | google/gemma-4-31B | 32682 | 0.047 | 0.5% | 108.5 | 0.76 |
| 4 | AutoJev-27B | 56.4 | full fine-tune | Qwen/Qwen3.8-27B | 27781 | 0.018 | 0.8% | 101.4 | 0.76 |
| 5 | simple-jev · Qwen3.8-27B (featherless) | 55.7 | inference technique | Qwen/Qwen3.8-27B | 27781 | 0.113 | 3.9% | 373.0 | 0.76 |
| 6 | Jebadiah 27B | 54.7 | LoRA | Qwen/Qwen3.8-27B | 27781 | 0.014 | 0.7% | 110.4 | 0.76 |
| 7 | reflex 27B (FP8 · wide choice) | 52.2 | inference technique | Qwen/Qwen3.8-27B | 27781 | 0.024 | 0.9% | 108.3 | 0.76 |
| 8 | Decider chat · Qwen3.6-27B | 51.4 | inference technique | Qwen/Qwen3.6-27B | 27781 | 0.021 | 0.1% | 83.6 | 0.76 |
| 9 | Winnow-12B (Q8_0) | 50.0 | LoRA | google/gemma-4-12B | 11960 | 0.168 | 6.2% | 72.5 | 0.76 |
| 10 | JoshuaSP diffusiongemma (open-jev) | 49.5 | inference technique | google/diffusiongemma-26B-A4B-it | 25824 | 0.215 | 13.7% | 260.4 | 0.76 |
| 11 | Jevfire | 49.4 | inference technique | Qwen/Qwen3.8-27B | 27781 | 0.052 | 1.5% | 89.6 | 0.76 |
| 12 | Decider 35B-A3B (NVFP4) | 47.1 | full fine-tune | Qwen/Qwen3.5-35B-A3B-Base | 35952 | 0.023 | 0.4% | 101.4 | 0.76 |
| 13 | JPT-9B | 46.9 | LoRA | Qwen/Qwen3.5-9B-Base | 9653 | 0.077 | 1.8% | 148.6 | 0.76 |
| 14 | Decision 1.0 Lux | 43.5 | head / adapter | Qwen/Qwen3.5-9B-Base | 9653 | 0.076 | 1.7% | 51.0 | 0.76 |
| 15 | Xor | 41.5 | full fine-tune | Qwen/Qwen3.6-35B-A3B | 35952 | 0.015 | 0.4% | 139.9 | 0.69 |
| 16 | Decider 4B | 40.7 | full fine-tune | Qwen/Qwen3.5-4B-Base | 4660 | 0.084 | 1.8% | 12.6 | 0.76 |
| 17 | Jev-Omni | 40.5 | LoRA + head | google/gemma-4-12B | 11960 | 0.161 | 5.5% | 54.9 | 0.76 |
| 18 | djev | 40.3 | inference technique | google/diffusiongemma-26B-A4B-it | 25824 | 0.212 | 8.2% | 84.4 | 0.76 |
| 19 | Winnow-E4B (Q8_0) | 39.9 | LoRA | google/gemma-4-E4B | 7996 | 0.058 | 0.7% | 45.0 | 0.76 |
| 20 | Hopper | 39.7 | LoRA | Qwen/Qwen3.5-4B-Base | 4660 | 0.083 | 0.2% | 23.3 | 0.76 |
| 21 | Bespoke Nimble 9B v2 | 39.6 | LoRA | Qwen/Qwen3.5-9B-Base | 9653 | 0.024 | 0.2% | 77.3 | 0.76 |
| 22 | JevK5 | 38.8 | LoRA | Qwen/Qwen3.5-4B-Base | 4660 | 0.027 | 0.5% | 22.0 | 0.76 |
| 23 | lev | 38.5 | LoRA + head | Qwen/Qwen3.5-4B-Base | 4660 | 0.064 | 1.2% | 70.8 | 0.76 |
| 24 | Kev 9B | 38.5 | LoRA + head | Qwen/Qwen3.5-9B-Base | 9653 | 0.138 | 5.5% | 51.4 | 0.76 |
| 25 | Intern-Decision-4B | 37.8 | full fine-tune | Qwen/Qwen3.5-4B-Base | 4660 | 0.028 | 0.2% | 44.2 | 0.76 |
| 26 | razorback16 openjev diffusiongemma (NVFP4, vLLM) (one read, NVFP4) | 37.2 | inference technique | google/diffusiongemma-26B-A4B-it | 25824 | 0.232 | 11.4% | 37.7 | 0.76 |
| 27 | NeoHorse-Jev-4B | 36.8 | head / adapter | Qwen/Qwen3.5-4B-Base | 4660 | 0.104 | 2.8% | 49.0 | 0.76 |
| 28 | Solomon v1.1 | 36.4 | head / adapter | Qwen/Qwen3.8-27B | 27781 | 0.081 | 3.0% | 223.9 | 0.60 |
| 29 | Kev 4B | 34.6 | LoRA + head | Qwen/Qwen3.5-4B-Base | 4660 | 0.176 | 7.2% | 52.1 | 0.76 |
| 30 | Decision 1.0 Nox | 34.4 | head / adapter | Qwen/Qwen3.5-4B-Base | 4660 | 0.140 | 4.9% | 53.2 | 0.76 |
| 31 | Jobe | 32.4 | inference technique | Qwen/Qwen3.5-4B-Base | 4660 | 0.123 | 2.3% | 53.5 | 0.76 |
| 32 | mmastrac diffusiongemma (vLLM PR 57250) | 32.2 | inference technique | google/diffusiongemma-26B-A4B-it | 25824 | 0.202 | 9.1% | 126.7 | 0.69 |
| 33 | open-jev (pngwn) | 29.9 | LoRA | Qwen/Qwen3.5-4B-Base | 4660 | 0.059 | 1.5% | 112.3 | 0.76 |
| 34 | Tev1-4B-experimental | 29.2 | full fine-tune | Qwen/Qwen3.5-4B-Base | 4660 | 0.104 | 1.7% | 35.8 | 0.69 |
| 35 | Decider 2B (FP8) | 29.0 | full fine-tune | Qwen/Qwen3.5-2B-Base | 2274 | 0.077 | 1.0% | 8.1 | 0.76 |
| 36 | openvons | 28.4 | inference technique | Qwen/Qwen3-4B-Instruct-2507 | 4022 | 0.371 | 30.5% | 21.2 | 0.76 |
| 37 | this-that 1.2 | 28.1 | full fine-tune | Mapika/decider-2b | 1882 | 0.198 | 7.8% | 44.3 | 0.76 |
| 38 | Metask-Jev-4B | 26.9 | LoRA | Qwen/Qwen3.5-4B-Base | 4660 | 0.103 | 0.4% | 57.3 | 0.69 |
| 39 | SemIf | 25.9 | inference technique | Qwen/Qwen3.5-4B-Base | 4660 | 0.099 | 2.6% | 113.1 | 0.69 |
| 40 | Decision 1.0 Sol | 25.3 | head / adapter | Qwen/Qwen3.5-2B-Base | 2274 | 0.115 | 2.2% | 38.1 | 0.76 |
| 41 | mini-jev | 21.0 | inference technique | Qwen/Qwen3-4B-Instruct-2507 | 4022 | 0.346 | 27.3% | 66.9 | 0.69 |
| 42 | Bosun v3.1 1.7B | 20.1 | LoRA + head | Qwen/Qwen3-1.7B-Base | 1721 | 0.130 | 2.7% | 40.3 | 0.76 |
| 43 | Intern-Decision-2B | 19.4 | full fine-tune | Qwen/Qwen3.5-2B-Base | 2274 | 0.061 | 0.0% | 33.5 | 0.76 |
| 44 | JPT-0.8B | 19.2 | LoRA | Qwen/Qwen3.5-0.8B-Base | 873 | 0.069 | 0.4% | 117.5 | 0.76 |
| 45 | Decision 1.0 Eos | 18.4 | head / adapter | Qwen/Qwen3.5-0.8B-Base | 873 | 0.083 | 0.5% | 39.7 | 0.76 |
| 46 | Kev 0.8B | 14.6 | LoRA + head | Qwen/Qwen3.5-0.8B-Base | 873 | 0.074 | 0.4% | 41.6 | 0.76 |
| 47 | Bosun v3.1 0.6B | 14.3 | LoRA + head | Qwen/Qwen3-0.6B-Base | 596 | 0.142 | 0.8% | 38.7 | 0.76 |
| 48 | Tev1-0.8B-experimental | 12.8 | full fine-tune | Qwen/Qwen3.5-0.8B-Base | 873 | 0.126 | 1.2% | 28.5 | 0.69 |
| 49 | Intern-Decision-0.8B | 11.9 | full fine-tune | Qwen/Qwen3.5-0.8B-Base | 873 | 0.025 | 0.0% | 33.7 | 0.76 |
| 50 | MoJev | 11.7 | head / adapter | Qwen/Qwen3.5-0.8B-Base | 873 | 0.125 | 1.1% | 46.4 | 0.76 |
| 51 | GLiNER2.5-Decide | 11.2 | full fine-tune | fastino/gliner2-large-v1 | 486 | 0.088 | 1.3% | 23.3 | 0.76 |
| 52 | Lavoir | 8.7 | full fine-tune | answerdotai/ModernBERT-large | 396 | 0.149 | 2.4% | 20.0 | 0.76 |
| 53 | jeff | 8.0 | inference technique | knowledgator/gliformer-large-v1 | 576 | 0.097 | 0.0% | 21.8 | 0.76 |
| 54 | CLM-v0.1-8B | 7.4 | full fine-tune | Qwen/Qwen3-8B-Base | 8191 | 0.323 | 11.9% | 46.8 | 0.76 |
| 55 | GLiNER 2.5 base | 6.8 | full fine-tune |  | 194 | 0.367 | 16.7% | 14.1 | 0.76 |
| 56 | LFM2.5-2.6B-RLCD | 6.8 | full fine-tune | LiquidAI/LFM2.5-2.6B-Base | 2697 | 0.255 | 5.1% | 39.3 | 0.74 |
| 57 | Decision 1.0 Kai | 6.5 | head / adapter | jhu-clsp/mmBERT-base | 308 | 0.185 | 0.4% | 30.4 | 0.76 |
| 58 | Laya | 6.0 | full fine-tune |  | 421 | 0.140 | 1.2% | 5.8 | 0.76 |
| 59 | Julia 1 | 5.5 | full fine-tune | jhu-clsp/mmBERT-small | 141 | 0.420 | 18.7% | 5.8 | 0.76 |
| 60 | system-one-gemma | 5.1 | LoRA + head | google/gemma-3-270m | 268 | 0.239 | 1.6% | 31.9 | 0.76 |
| 61 | Decision 1.0 Lex | 4.5 | head / adapter | jhu-clsp/mmBERT-base | 308 | 0.169 | 0.1% | 29.8 | 0.76 |
| 62 | GLiNER 2.5 multilingual | 4.3 | full fine-tune |  | 287 | 0.254 | 4.8% | 14.0 | 0.76 |
| 63 | GLiNER 2.5 small | 3.8 | full fine-tune |  | 74 | 0.161 | 2.4% | 13.6 | 0.76 |
| 64 | Qwen-2.5-1B-RLCD | 3.8 | inference technique | Qwen/Qwen2.5-1.5B | 1544 | 0.205 | 3.5% | 43.8 | 0.76 |
| 65 | Lumma-Fev-0.6B | 3.0 | LoRA | FrontiersMind/Lumma-0.6B-Base | 649 | 0.236 | 5.6% | 21.3 | 0.76 |
| 66 | Verdict | 1.9 | full fine-tune | knowledgator/gliclass-modern-base-v2.0 | 151 | 0.154 | 0.0% | 11.4 | 0.31 |
| 67 | Lumma-Fev-0.1B | 1.8 | full fine-tune | FrontiersMind/Nandi-Mini-150M | 153 | 0.157 | 0.3% | 20.9 | 0.71 |
| 68 | LFM2.5-350M-RLCD | 1.4 | full fine-tune |  | 354 | 0.568 | 33.8% | 26.7 | 0.76 |
