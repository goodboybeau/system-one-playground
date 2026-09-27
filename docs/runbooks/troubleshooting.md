# Troubleshooting

Start with `make doctor`. Engine logs are in `.run/logs/<engine>.log`, also available from the **Log** button on each
engine card.

| Symptom | Cause | Fix |
|---|---|---|
| `make lab` says the address is in use | Something else is on port 8080 | `uv run --project gateway lab --port 8090 --open` |
| Engine card says **Weights not downloaded** | That engine's model isn't in the Hugging Face cache | `make weights` (small models) or `make weights-all` |
| **Needs about N GB and M GB is free** | The memory guard, based on the engine's last peak or its size | Stop another engine, close a heavy app, or click *Start anyway* |
| Engine shows **failed** with a traceback | Load error: often out of memory, sometimes a corrupt download | Read the log. For a corrupt download: `rm -rf ~/.cache/huggingface/hub/models--<org>--<name>` and `make weights-all` |
| Engine shows **crashed** | The process exited; usually the OS killed it for memory | Check the log's last lines. Run the 4B models one at a time on 32 GB Macs |
| Decider, Kev or Qwen take 9–13 s per request | They're on `cpu`; Qwen3.5's recurrent layers have no fast CPU kernels | Stop, pick `mps` (Decider, Qwen) or `mlx` (Kev), start again |
| First request after start is slow (0.3–1 s) | Metal compiles kernels for each new input shape | Use `repeat` in the Playground for steady-state numbers |
| `make setup` says some slices couldn't be fetched | The Hugging Face datasets server rate-limits | Run `make datasets` again later. Everything else works meanwhile |
| `make weights` stalls or fails | Hugging Face rate limit for anonymous downloads | `export HF_TOKEN=hf_…` (a free read token) and rerun |
| Engine can't reach the internet | That's the sandbox working. Local engines run offline by design | Download weights first. For debugging only: `uv run --project gateway lab --no-sandbox` |
| Benchmark took far longer than its latencies add up to | The Mac slept. Jobs hold a `caffeinate` assertion, but a closed lid still sleeps | Keep the lid open (or use clamshell mode with power) during `make suite` |
| Leftover `labkit.serve` processes | Shouldn't happen: engines exit when the gateway dies and stale ones are killed on start | `pkill -f labkit.serve` |
| Start from scratch | | Stop the lab, then `rm -rf .run`. Runs, cold starts and logs are gone; weights and datasets stay |
