# What the numbers mean

## Per request

| Metric | How it's measured |
|---|---|
| **Wall** | Gateway → engine → gateway round trip on localhost. What an app calling the engine would see. |
| **Model** | Time inside the engine's `predict`, excluding HTTP and JSON. |
| **Queue** | Time a request waited for the engine's single worker. Zero when requests arrive one at a time. |
| **CPU time** | CPU seconds the engine process used during the request, from `psutil` user and system time. On MPS/MLX most work runs on the GPU, so this is low even for big models. |
| **Tokens** | Input tokens as the engine reports them. Output tokens are always 0: these models don't generate. |

## Per engine process

| Metric | How it's measured |
|---|---|
| **Footprint** | Physical footprint from `proc_pid_rusage`, which Activity Monitor calls "Memory". On Apple Silicon it includes Metal buffers in unified memory; **RSS does not**. Decider 2B shows 0.27 GB of RSS but a 5.6 GB footprint. Sampled every 250 ms. |
| **Peak** | Highest footprint seen since start, usually during load. The memory guard uses the peak from earlier runs to warn before a start that won't fit. |
| **CPU %** | Change in process CPU time between samples; 100% is one core busy. |
| **GPU %** | Apple GPU utilisation from `ioreg`'s IOAccelerator statistics. **System-wide**: macOS doesn't attribute GPU time per process without root. |
| **Cold start** | Split into *process* (spawn → HTTP port open: Python and torch imports), *load* (weights into memory) and *warm-up* (first request, which compiles Metal kernels). |

## Benchmarks

Calibration metrics use `p_top`, the probability the engine put on the answer it chose.

| Metric | Definition |
|---|---|
| **Accuracy** | Correct over all items. An item the engine couldn't answer (an error such as too many options) counts as wrong. |
| **Answered** | Share of items answered without an error. |
| **ECE** | Expected calibration error: split answers into 10 bins by confidence, then take the weighted mean of \|accuracy − confidence\|. 0 means "90% confident" is right 90% of the time. |
| **Brier** | Mean squared error of the full probability distribution against the one-hot correct answer. Rewards both being right and being honest about uncertainty. |
| **Wrong @95%** | Share of answers that were wrong while the engine claimed ≥95% confidence. The dangerous errors. |
| **Auto @95%** | The largest share of items you could accept automatically, most confident first, while staying ≥95% accurate. This is the "how much can I automate at a 5% error budget" number. |
| **MAE** | Score questions only: mean absolute distance between the expected level and the correct level. |

Choice answers count as correct when the top option matches. Score answers count when the most likely level matches.
Yes/no answers count when P(yes) ≥ 0.5 agrees with the label.

## Confidence

Engines define "confidence" differently. Laya uses 1 − normalised entropy; Decider and Kev use TypeSafe's formula. So
the playground recomputes it from the probabilities with TypeSafe's definition:
- **choice:** (n · p_max − 1) / (n − 1);
- **score:** 1 − the expected distance from the most likely level, divided by the scale's mean distance from its middle;
- **yes/no:** |2p − 1|, since TypeSafe defines none.

Each engine's own value is kept in the raw response.

## Fairness rules

- Benchmarks run **one engine at a time**, and only one job runs at once.
- While a job runs, the gateway holds a `caffeinate` assertion: a Mac that sleeps mid-benchmark freezes every clock.
- Parallel mode in the Playground is labelled as including contention.
- Numbers are only comparable on the same machine. Chart and card labels state the device (`mps`, `mlx`, `cpu`).
