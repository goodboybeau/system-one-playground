# Benchmark slices

Each file is a fixed, seeded 200-item sample of a public dataset's test split (seed 7), one JSON object per line:

```json
{"id": "b10-0", "state": "How do I locate my card?", "question": {"type": "choice", "instructions": "...", "criteria": {...}}, "gold": "card_arrival"}
```

`gold` is an option label for `choice`, a level index for `score`, and `true`/`false` for `noul`. Every item is checked against the `/v1/systemone` contract when it is built and when it is loaded.

| Slice | Task | Source | Source license | In this repo |
|---|---|---|---|---|
| `banking10` | choice (10 intents) | [PolyAI Banking77](https://huggingface.co/datasets/PolyAI/banking77) via [mteb/banking77](https://huggingface.co/datasets/mteb/banking77) | CC-BY-4.0 | yes |
| `banking77` | choice (77 intents, stress test) | same | CC-BY-4.0 | yes |
| `prompt_injections` | yes/no | [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) | Apache-2.0 | yes |
| `pubmedqa` | yes/no over long abstracts | [qiaojin/PubMedQA](https://huggingface.co/datasets/qiaojin/PubMedQA) | MIT | yes |
| `massive` | choice (18 scenarios, 6 languages) | [Amazon MASSIVE](https://huggingface.co/datasets/AmazonScience/massive) via [mteb/amazon_massive_scenario](https://huggingface.co/datasets/mteb/amazon_massive_scenario) | CC-BY-4.0 | yes |
| `ag_news` | choice (4 topics) | [fancyzhx/ag_news](https://huggingface.co/datasets/fancyzhx/ag_news) | not stated | fetched by `make setup` |
| `emotion` | choice (6 emotions) | [dair-ai/emotion](https://huggingface.co/datasets/dair-ai/emotion) | "other" | fetched by `make setup` |
| `sst5` | score (5 levels) | [SetFit/sst5](https://huggingface.co/datasets/SetFit/sst5) | not stated | fetched by `make setup` |
| `sms_spam` | yes/no | [ucirvine/sms_spam](https://huggingface.co/datasets/ucirvine/sms_spam) | not stated | fetched by `make setup` |

The bundled slices keep their source licenses; the project's MIT license does not apply to them. Slices whose source doesn't state
redistribution terms are not committed. `make datasets` rebuilds them from the source, and the sampling is
deterministic, so everyone gets byte-identical files.

To add your own, drop a `.jsonl` file here in the format above. It shows up on the Benchmarks page immediately. See
[docs/howto/add-a-dataset.md](../docs/howto/add-a-dataset.md).
