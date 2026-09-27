# Using Jev (TypeSafe)

Jev is the hosted model that started the category. The playground treats it as one more engine behind a small proxy, so
it shows up in the Playground, Benchmarks and Load test like everything else.

## Get a key

1. Sign up at **https://console.typesafe.ai**. There's no waitlist, and new accounts get $5 of credit (about 120M input tokens at $0.042 per million; output is free).
2. Open **Settings → API keys** (https://console.typesafe.ai/settings/keys), create a key and copy it.
3. In the repo: `cp .env.example .env`, then set `TYPESAFE_API_KEY=…`.
4. The Jev card on **Engines** unlocks within a couple of seconds; no restart needed. Click **Start**.

## What to know

- **Data leaves your machine.** Everything you send to the Jev engine goes to TypeSafe. Local engines never make network calls; Jev is the one exception, and its card says so.
- **The key stays with Jev.** Only the Jev proxy process receives `TYPESAFE_API_KEY`. Local engines get a clean environment.
- **The model is pinned** to `jev-1.13.0`, not `jev-latest`, which has changed answers between runs. To try another version, change `model` in `engines.toml`.
- **Costs are tiny but real.**
  - A 100-item benchmark on one dataset uses roughly 10–30k tokens, well under a cent.
  - Load tests multiply that, and count against the rate limit (1,200 requests/minute).
- **The proxy retries** 429 and 529 responses with backoff, three times.
- **Its CPU and memory numbers are the proxy's**, not the model's. Latency includes your network round trip.

## Check it

```bash
make verify ENGINES_TO_VERIFY=jev      # with the lab running: conformance suite against the live API
make suite SUITE_ENGINES=jev           # add Jev to the leaderboard
```
