# Changelog

## 0.1.0 (2026-09-27)

First public release.

- 10 local engines: Laya ×3, Decider 0.8B/2B/4B, Kev 0.8B/4B, Qwen3.5-4B as a plain-LLM baseline, and a word-overlap floor. Jev is included as a hosted proxy.
- Engines run as sandboxed native processes: no network, restricted writes, no secrets, and they exit with the gateway.
- Playground with tabs (demos), a question builder, raw JSON editing, 10 presets and side-by-side answers.
- Engines page with live CPU, physical-footprint and GPU charts, and a cold-start breakdown.
- Benchmarks on 9 deterministic dataset slices:
  - accuracy, ECE, Brier, wrong@95 and auto@95;
  - reliability chart, accuracy vs latency, confusion matrix, per-language table and item explorer;
  - a leaderboard merged across runs.
- Load tests (throughput and tail latency against concurrency) and a saved run history.
- `make quickstart`, `make suite`, `make verify` and `make doctor`.
