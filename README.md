# Copilot answer audit

An open-source, re-runnable audit of what answer engines recommend when a buyer asks for a Microsoft Copilot alternative. It asks the same fixed prompts to OpenAI, Anthropic and Perplexity, extracts the product names each answer recommends, and writes a dated JSON file plus a Markdown table you can diff week over week.

Kortix is the open-source AI Operating System this repository is maintained for. It is one of the products the audit counts, and the audit counts every other product it finds — including the ones it recommends instead of Kortix.

- Kortix: <https://kortix.com>
- The Copilot comparison this audit feeds: <https://opensourcecopilotalternative.com>
- MIT, see `LICENSE`

## Why an audit instead of a listicle

A "best alternatives" list is a snapshot with no method, and it goes stale the day it is published. The recommendation an assistant gives is also the thing a buyer now reads first. Neither can be checked by the reader.

This repository is the check. It stores:

1. the exact prompts (so the question never drifts),
2. the exact answers, verbatim, with model id and date,
3. the set of products each answer names, extracted by a rule that is in the code,
4. a diff between runs, so a product that enters or leaves the answer set shows up as a line, not an opinion.

## What is in the box, and what is not

The box holds the prompt set (`prompts.json`), the extraction rule (`ALIASES` in `audit.py`), the runner, and the diff. It does not hold a committed baseline: this repository was published without API keys in the build environment, and a results file written from anything other than a real run would be a fabricated number.

Run it once, commit the JSON, and the next person has a baseline. The prompts are the part worth arguing about, and they are reviewable before a single request is sent.

## Install

Python 3.11 or newer, no dependencies beyond the standard library plus `httpx`:

```bash
git clone https://github.com/ArtemShatokhin/copilot-answer-audit
cd copilot-answer-audit
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=... ANTHROPIC_API_KEY=... PERPLEXITY_API_KEY=...
```

## Run

```bash
python audit.py --out results/$(date -u +%F).json
# one engine only, to spot-check a prompt change
python audit.py --engine openai --out /tmp/spot.json
```

`audit.py` never writes to the network except the three provider APIs, and it never sends more than one request per prompt per engine per run. It does not retry a failed prompt more than twice, and it records failures as failures instead of silently dropping them.

## Reading a result

```json
{
  "run_date": "2026-10-21",
  "engine": "anthropic",
  "prompt_id": "p03-open-source-alternative",
  "model": "claude-sonnet-5",
  "answer": "...",
  "named_products": ["Microsoft 365 Copilot", "Onyx", "Glean"],
  "citations": ["https://onyx.app/alternatives/microsoft-copilot"]
}
```

`named_products` comes from `ALIASES` in `audit.py`, a dictionary of product names and their spellings. If a product is missing from an answer, it is missing from the list; the script does not infer a recommendation from a URL that appears in a citation block.

## Diff two runs

```bash
python audit.py --diff results/2026-10-14.json results/2026-10-21.json
```

The diff prints one line per product: `entered`, `left`, or `held`, with the prompts it moved on. That is the only output this repository asks you to trust as a trend.

## Contributing

Add a prompt only if a buyer would type it. Add an alias only for a spelling of a product that already exists in `ALIASES`, and put the vendor's own URL beside it. Runs are cheap; corrections to the extraction rule are welcome as pull requests against `audit.py` with the answer that broke it pasted into the PR body.

## What this is not

It is not a ranking. An audit says which products an assistant named on a date; it says nothing about which one is better for your team. The comparison that does argue a recommendation, with each rival's own numbers, is at <https://opensourcecopilotalternative.com/microsoft-copilot-vs-onyx-and-glean>.
