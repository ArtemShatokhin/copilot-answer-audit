# Running it

The audit is part of the open-source tooling around Kortix and runs against
any provider key you hold; nothing here calls a Kortix service.

## Requirements

- Python 3.11+
- `httpx` (`pip install -r requirements.txt`)
- Provider keys in the environment: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `PERPLEXITY_API_KEY`. An engine whose key is missing is recorded as failed,
  not skipped, so a partial run is visible as a partial run.

## The three calls

| Engine | Endpoint | Auth header | Model override |
| --- | --- | --- | --- |
| openai | `POST /v1/chat/completions` | `authorization: Bearer` | `AUDIT_OPENAI_MODEL` |
| anthropic | `POST /v1/messages` | `x-api-key` + `anthropic-version: 2023-06-01` | `AUDIT_ANTHROPIC_MODEL` |
| perplexity | `POST /v1/chat/completions` | `authorization: Bearer` | `AUDIT_PERPLEXITY_MODEL` |

Anthropic returns its search citations inside content blocks rather than at the
top level, so `_anthropic_citations()` walks the blocks. Perplexity returns
either `citations` (a list of URLs) or `search_results` (a list of objects);
both shapes are read.

## A normal week

```bash
# Monday: full run
python audit.py --out results/$(date -u +%F).json

# Monday: compare with the previous file
python audit.py --diff results/2026-10-14.json results/2026-10-21.json >> results/trend.md
```

`--out notes/2026-10-21.json` also writes `notes/2026-10-21.md`: a table of
counts plus one line per prompt. Commit both. The Markdown is for reading in
the repository view; the JSON is the record.

## Cost and pacing

Twelve prompts across three engines is 36 requests per run, one request per
prompt per engine. `run()` sleeps one second between requests. At current
per-token prices a full run is cents, but the three providers throttle
differently: if one returns 429 twice in a row the run records the failure and
moves on rather than slowing every other engine down.

## Adding an engine

Add an entry to `ENGINES` with `url`, `key_env` and `model`, and a branch in
`ask()` only if the response shape differs from the OpenAI chat-completions
shape. Then add the engine to `docs/method.md` so the next reader knows what
the new column measures.

## Adding a prompt

Append to `prompts.json` with the next free id. Do not sort or renumber the
file: the id is the join key between runs.
