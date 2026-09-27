# Add an engine

An engine is a uv project with a `load()` function. labkit turns it into a `/v1/systemone` server; the gateway runs it
in the sandbox and measures it.

## 1. Create the project

```bash
mkdir -p engines/myengine && cd engines/myengine
uv init --bare --python 3.12 --name engine-myengine
uv add --editable ../../labkit
uv add <your model's packages>
uv add --dev pytest
```

Add this to its `pyproject.toml` so tests can import the adapter:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

## 2. Write the adapter: `engines/myengine/engine_myengine.py`

```python
from typing import Any


class MyPredictor:
    def __init__(self, model: str, device: str):
        self.model = load_your_model(model, device)       # weights come from the HF cache; the sandbox is offline

    def info(self) -> dict[str, Any]:
        return {"backend": "torch 2.x", "params": 123_000_000, "dtype": "float16"}

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "choice":                     # criteria is always a {label: description | None} map
                answers[qid] = {"probabilities": {label: p for label, p in ...}}
            elif q["type"] == "score":                    # criteria is an ordered list of level descriptions
                answers[qid] = {"probabilities": {"0": p0, "1": p1}}   # keys: level index or level text
            else:                                         # noul: yes/no
                answers[qid] = {"noul": p_true}
        return {"answers": answers, "usage": {"input_tokens": n}, "warnings": []}


def load(model: str, device: str, threads: int | None) -> MyPredictor:
    return MyPredictor(model, device)
```

Rules the contract enforces:
- Probabilities must be finite, sit in [0, 1], and sum to 1 (±2%).
- Every option or level must be present.
- Raise `ValueError` for input the model can't handle (for example, too many options). It becomes a 422 with your message; other exceptions become a 500.
- Put anything the user should know about a request, such as truncated input, in `warnings`. The UI shows it.

You don't need to compute `confidence`, the chosen label or the expected score: labkit derives them from the
probabilities so every engine is compared the same way.

## 3. Register it in `engines.toml`

```toml
[[engine]]
id = "myengine"
label = "My Engine 1B"
project = "engines/myengine"
loader = "engine_myengine:load"
model = "org/my-engine-1b"
devices = ["mps", "cpu"]            # the first one is the default
params = 1_000_000_000
architecture = "what it is, in one line"
license = "Apache-2.0"
source = "https://huggingface.co/org/my-engine-1b"
weights = ["org/my-engine-1b"]      # repos to download; "repo:subfolder" counts only part of a repo
note = "Anything a user should know before starting it."
```

Then:
1. Add `myengine` to `ENGINES` in the `Makefile`, so `make setup` installs it.
2. Add its repos to `scripts/download-weights.sh`.
3. Optionally, give it a colour slot in `ui/src/lib/colors.ts`. Otherwise it's drawn in neutral grey.

## 4. Prove it

```bash
make setup && make weights-all
make lab                                    # then, in another terminal:
make verify ENGINES_TO_VERIFY=myengine      # 12 contract checks, inside the sandbox
make suite SUITE_ENGINES=myengine           # benchmark it on every dataset
```

If the model needs to write somewhere unusual, or the sandbox blocks something it legitimately needs, the log shows an
`Operation not permitted` error. Open an issue rather than widening the sandbox in your PR.
