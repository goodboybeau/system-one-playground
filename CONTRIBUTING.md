# Contributing

Thanks for helping. The most useful contributions are **new engines**, **new datasets**, **benchmark results from other
Macs**, and bug reports with a way to reproduce them.

## Set up

```bash
git clone https://github.com/goodboybeau/system-one-playground
cd system-one-playground
make doctor && make setup
make weights        # optional: small models, ~6 GB
make dev            # gateway on :8080, UI with hot reload on :5173
```

## Before you open a pull request

```bash
make test           # contract, gateway, Jev proxy, UI unit tests, typecheck, Playwright
make test-engines   # only if you touched an engine adapter (needs its weights)
make verify         # only if you touched an engine: runs the conformance suite inside the sandbox
```

CI runs `make test`'s pieces on Apple Silicon runners. A PR should keep it green.

## How the code is laid out

| Path | What lives there |
|---|---|
| `labkit/` | The one contract: request parsing, answer normalisation, the engine HTTP server, the conformance suite, a mock engine |
| `engines/<name>/` | One uv project per model family, each with its own virtualenv and a small adapter (`engine_<name>.py`) |
| `engines.toml` | The registry: every engine the UI can start |
| `gateway/` | FastAPI app: supervisor, sandbox, sampler, benchmarks, load tests, storage, and the built UI |
| `ui/` | React, TypeScript, Recharts and CodeMirror; Playwright tests in `ui/e2e/` |
| `datasets/`, `presets/` | Benchmark slices and playground examples |
| `docs/` | Architecture, runbooks, how-tos, and research notes |

Read [docs/architecture.md](docs/architecture.md) before changing the gateway or labkit.

## Conventions

- **Everything crosses one boundary**: TypeSafe's `POST /v1/systemone` shape, validated by `labkit.contract`. Engine quirks stay inside the adapter; the gateway and UI never special-case an engine.
- **Measure honestly.**
  - Label every number with what it measures and on what hardware.
  - Don't compare parallel runs.
  - Use physical footprint, not RSS, on Apple Silicon.
- **Tests pin behaviour, not internals.** Gateway tests start real engine processes (mock ones), and the UI is tested through a real browser.
- **Code style**: match what's there. No comments that restate the code; docstrings explain *why*.
- **Commits**: small and focused, with an imperative subject ("Add Kev 9B engine").

## Adding things

- A new engine: [docs/howto/add-an-engine.md](docs/howto/add-an-engine.md)
- A new dataset: [docs/howto/add-a-dataset.md](docs/howto/add-a-dataset.md)
- A new preset: [docs/howto/add-a-preset.md](docs/howto/add-a-preset.md)

## Sharing benchmark results

Run `make suite`, then open an issue with the **Benchmark results** template. Include your chip, memory, macOS version,
and the table from the Benchmarks overview (the Export JSON button is handy). Results from different chips are how
this project gets more useful.

By contributing you agree that your contributions are licensed under the MIT license, and you follow the
[code of conduct](CODE_OF_CONDUCT.md).
