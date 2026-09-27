# Add a dataset

Drop a JSONL file into `datasets/`. Each line is one item:

```json
{"id": "t-1", "state": "The app crashes when I open settings", "question": {"type": "choice", "instructions": "What kind of report is this?", "criteria": {"bug": "something is broken", "feature": "a request for something new"}}, "gold": "bug"}
```

- **`state`**: a string, object or array, exactly as an engine would receive it.
- **`question`**: one `/v1/systemone` question. Keep it identical across items so results are comparable.
- **`gold`**:
  - an option label for `choice`;
  - a 0-based level index for `score`;
  - `true`/`false` for `noul`.
- **`lang`** (optional): enables the per-language accuracy table.

It appears on the Benchmarks page right away. Every item is validated against the contract when loaded, so a
malformed line gives an error that names the line.

To give it a nice title, description and label order, add an entry to `datasets/index.json`:

```json
"mydata": {"title": "My tickets", "task": "choice", "labels": ["bug", "feature"], "source": "internal", "description": "What it measures.", "items": 200}
```

To publish a new public slice, add a builder to `gateway/src/gateway/fetch_datasets.py`. The existing builders show the
pattern: a seeded sample from a Hugging Face test split, balanced by label. Then add a row to `datasets/README.md`
with the source license. Only commit the JSONL if that license allows redistribution; otherwise add it to
`.gitignore` so `make setup` fetches it.
