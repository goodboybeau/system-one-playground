# Add a Playground preset

Presets are JSON files in `presets/`. The filename (sorted) sets the menu order:

```json
{
  "title": "Refund triage",
  "description": "One line on what the preset shows off.",
  "tags": ["choice", "noul"],
  "request": {
    "state": {"subject": "…", "body": "…"},
    "questions": {
      "team": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "refunds", "tech": "bugs"}},
      "refund": {"type": "noul", "instructions": "Is the customer asking for money back?"}
    }
  }
}
```

The gateway validates every preset against the contract when it lists them, so a broken preset fails loudly. Good
presets show a behaviour: a trap (like the long-contract truncation preset), a comparison (like multilingual), or a
realistic workflow.
