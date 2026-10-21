#!/usr/bin/env python3
"""Ask the same fixed prompts to three answer engines and record which products
each answer recommends.

    python audit.py --out results/2026-10-21.json
    python audit.py --engine openai --prompt p03 --out /tmp/spot.json
    python audit.py --diff results/a.json results/b.json

Design rules, in order of importance:

1. The prompts are fixed and stored (prompts.json). A prompt is added when a
   buyer would type it, never to make a product appear.
2. Answers are stored verbatim. `named_products` is extracted by ALIASES only;
   a citation URL is recorded separately and never counted as a recommendation.
3. A failure is recorded as a failure. Nothing is retried more than twice and
   nothing is dropped from the output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
ALIASES: dict[str, list[str]] = {
    "Kortix": ["kortix"],
    "Microsoft 365 Copilot": ["microsoft 365 copilot", "m365 copilot", "microsoft copilot"],
    "Microsoft Copilot Studio": ["copilot studio"],
    "GitHub Copilot": ["github copilot"],
    "Onyx": ["onyx"],
    "Glean": ["glean"],
    "Dust": ["dust"],
    "ChatGPT": ["chatgpt"],
    "Claude": ["claude"],
    "Gemini": ["gemini"],
    "Dify": ["dify"],
    "Flowise": ["flowise"],
    "n8n": ["n8n"],
    "Open WebUI": ["open webui", "openwebui"],
    "LibreChat": ["librechat"],
    "AnythingLLM": ["anythingllm"],
}

ENGINES = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
        "model": os.environ.get("AUDIT_OPENAI_MODEL", "gpt-5.2"),
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "key_env": "ANTHROPIC_API_KEY",
        "model": os.environ.get("AUDIT_ANTHROPIC_MODEL", "claude-sonnet-5"),
    },
    "perplexity": {
        "url": "https://api.perplexity.ai/chat/completions",
        "key_env": "PERPLEXITY_API_KEY",
        "model": os.environ.get("AUDIT_PERPLEXITY_MODEL", "sonar-pro"),
    },
}


def ask(engine: str, prompt: str, timeout: float = 90.0) -> dict:
    """One request to one engine. Returns {answer, citations, model, error}."""
    cfg = ENGINES[engine]
    key = os.environ.get(cfg["key_env"], "")
    if not key:
        return {"answer": "", "citations": [], "model": cfg["model"],
                "error": f"{cfg['key_env']} not set"}
    last = ""
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                if engine == "anthropic":
                    r = client.post(cfg["url"], headers={
                        "x-api-key": key, "anthropic-version": "2023-06-01",
                        "content-type": "application/json"},
                        json={"model": cfg["model"], "max_tokens": 1200,
                              "messages": [{"role": "user", "content": prompt}]})
                else:
                    r = client.post(cfg["url"], headers={
                        "authorization": f"Bearer {key}",
                        "content-type": "application/json"},
                        json={"model": cfg["model"],
                              "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return {"answer": "", "citations": [], "model": cfg["model"],
                        "error": f"HTTP {r.status_code}: {r.text[:300]}"}
            body = r.json()
            if engine == "anthropic":
                text = "".join(b.get("text", "") for b in body.get("content", []))
                cites = _anthropic_citations(body)
            else:
                text = body["choices"][0]["message"]["content"]
                cites = [c.get("url") for c in
                         (body.get("citations") or body.get("search_results") or [])
                         if isinstance(c, dict) and c.get("url")]
            return {"answer": text, "citations": cites, "model": cfg["model"],
                    "error": None}
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            last = f"{type(exc).__name__}: {exc}"[:300]
            time.sleep(2 ** attempt)
    return {"answer": "", "citations": [], "model": cfg["model"], "error": last}


def _anthropic_citations(body: dict) -> list[str]:
    out = []
    for block in body.get("content", []):
        for c in block.get("citations", []) or []:
            url = c.get("url") or (c.get("document") or {}).get("url")
            if url:
                out.append(url)
    return out


def named(answer: str) -> list[str]:
    """Products the answer names. Whole-word, case-insensitive, aliases only.

    Whole-word means a regex word boundary, so "Glean," and "**Kortix**" both
    match while "gleaning" does not. Markdown noise is stripped first.
    """
    text = answer.lower().replace("*", "").replace("`", "")
    hits = []
    for product, aliases in ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                hits.append(product)
                break
    return hits


def run(engine_names: list[str], prompt_ids: list[str] | None = None) -> dict:
    prompts = json.loads((ROOT / "prompts.json").read_text())["prompts"]
    if prompt_ids:
        prompts = [p for p in prompts if p["id"] in prompt_ids]
    rows = []
    for engine in engine_names:
        for p in prompts:
            res = ask(engine, p["text"])
            rows.append({
                "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "engine": engine,
                "prompt_id": p["id"],
                "prompt": p["text"],
                "model": res["model"],
                "answer": res["answer"],
                "named_products": named(res["answer"]),
                "citations": res["citations"],
                "error": res["error"],
            })
            print(f"{engine:10s} {p['id']:32s} "
                  f"{'ERROR ' + (res['error'] or '')[:40] if res['error'] else ', '.join(named(res['answer']))[:60]}",
                  file=sys.stderr)
            time.sleep(1.0)
    ok = [r for r in rows if not r["error"]]
    return {
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompts": len(prompts),
        "engines": engine_names,
        "requests": len(rows),
        "failures": len(rows) - len(ok),
        "rows": rows,
        "named_counts": _counts(ok),
    }


def _counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        for product in r["named_products"]:
            counts[product] = counts.get(product, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def to_markdown(doc: dict) -> str:
    lines = [
        f"# Copilot answer audit — {doc['run_date']}",
        "",
        f"{doc['prompts']} fixed prompts, {', '.join(doc['engines'])}; "
        f"{doc['requests']} requests, {doc['failures']} failed.",
        "",
        "| Product | Answers naming it |",
        "| --- | --- |",
    ]
    for product, n in doc["named_counts"].items():
        lines.append(f"| {product} | {n} of {doc['requests']} |")
    lines += ["", "## Per prompt", ""]
    for r in doc["rows"]:
        if r["error"]:
            lines.append(f"- **{r['prompt_id']} / {r['engine']}** — failed: {r['error']}")
            continue
        names = ", ".join(r["named_products"]) or "none"
        lines.append(f"- **{r['prompt_id']} / {r['engine']}** — {names}")
    lines += ["", "Answers are stored verbatim in the JSON file beside this one.", ""]
    return "\n".join(lines)


def diff(old: dict, new: dict) -> str:
    a, b = set(old["named_counts"]), set(new["named_counts"])
    out = [f"# Diff {old['run_date']} -> {new['run_date']}", ""]
    for product in sorted(a & b):
        before, after = old["named_counts"][product], new["named_counts"][product]
        move = "held" if before == after else f"{before} -> {after}"
        out.append(f"- {product}: {move}")
    for product in sorted(b - a):
        out.append(f"- {product}: entered ({new['named_counts'][product]} answers)")
    for product in sorted(a - b):
        out.append(f"- {product}: left (was {old['named_counts'][product]} answers)")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", action="append", choices=sorted(ENGINES),
                    help="repeatable; default all three")
    ap.add_argument("--prompt", action="append", help="prompt id, repeatable")
    ap.add_argument("--out", help="JSON output path; a .md file is written beside it")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args()

    if args.diff:
        print(diff(json.loads(Path(args.diff[0]).read_text()),
                   json.loads(Path(args.diff[1]).read_text())))
        return 0
    if not args.out:
        ap.error("--out is required unless --diff is used")

    doc = run(args.engine or sorted(ENGINES), args.prompt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n")
    out.with_suffix(".md").write_text(to_markdown(doc))
    print(json.dumps({k: doc[k] for k in
                      ("run_date", "requests", "failures", "named_counts")}, indent=2))
    return 0 if doc["failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
