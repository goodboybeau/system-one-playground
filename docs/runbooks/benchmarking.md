# Running benchmarks

## Everything, unattended

```bash
make lab                      # in one terminal
make suite                    # in another: every installed engine × every dataset, 100 items each
make suite LIMIT=200          # full 200-item slices
make suite SUITE_ENGINES="laya-en kev-0.8b"
```

The suite starts one engine, runs every dataset through it, stops it, and moves to the next, so only one model is ever
in memory. It holds off idle sleep while it runs. Results appear live under **Benchmarks → All datasets**.

On an M1 Max with 100 items per slice:
- Laya and the word-overlap baseline take about a minute each.
- The 0.8B models take 1–3 minutes each.
- The 4B models take 4–7 minutes each.
- A full run of all ten local engines takes about half an hour.

## From the UI

1. Start the engines you want on **Engines**. Several can be running at once if they fit in memory.
2. On **Benchmarks**, pick a dataset and a size, select the running engines, and click **Run benchmark**. Engines still run one after another.
3. **This run** shows the fresh result. **Leaderboard across runs** merges the latest result per engine for the same dataset and size, so you can benchmark engines at different times as memory allows and still compare them.

## Reading the results

- Start with **Accuracy**, then check **Answered**. An engine that refuses items (Laya on huge option lists, for example) scores those items as wrong.
- **Wrong @95%** and **Auto @95%** say how far you can trust confidence for automation. **ECE** and the calibration chart show whether confidence means what it says. Pick one engine in the chart to read its curve.
- **Items → Split decisions** shows where engines disagree; click a row for the full input and each engine's top options.
- Compare against the **Word-overlap baseline**. On some tasks it's closer to the models than you'd expect.

Definitions are in [../metrics.md](../metrics.md).

## Comparing machines

Slices are deterministic (seed 7, byte-identical on every machine), so results from different Macs are directly
comparable on accuracy and calibration. Latency and memory are machine-specific: always state the chip. Please share
yours with the **Benchmark results** issue template.
