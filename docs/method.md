# Method

This document describes the measurement rule of an open-source tool: the
runner, the prompt set and the extraction rule are all in the repository, so a
reader can check the audit instead of trusting its table.

## The unit of measurement

One row is one answer: one engine, one prompt, one date. Nothing is averaged
across engines, because the engines do not agree and averaging three
recommendations produces a number that describes none of them.

## Prompts are fixed, and versioned by id

`prompts.json` holds twelve prompts a buyer would type about replacing
Microsoft Copilot. An id is never reused for different text: editing `p03` in
place silently changes the meaning of every earlier run of `p03`. Add `p13`
instead, and the diff will show the two as different rows.

The prompts avoid the audit's own bias. None names a product, none asks for a
ranking, and none is phrased so that only one answer can satisfy it.

## Extraction is a rule, not a judgement

`named()` lowercases the answer, strips Markdown emphasis and backticks, and
matches each product's aliases on word boundaries. It does not read the
citations block: an answer that links a vendor's page without recommending the
product is not counted as naming it, and an assistant that names a product
without linking it is counted.

That rule is deliberately dull, and it is the thing to argue with. If it
miscounts an answer, the correct response is a pull request that changes the
rule and pastes the answer that broke it into the PR body, not a hand-edited
JSON file.

## Failures stay in the output

A rate limit, a refusal or a 500 is written as a row with an `error` and no
products, and counted in `failures`. The alternative — retrying until it works
and keeping only the successes — biases the result toward whichever engine was
healthy that day.

`ask()` retries twice with exponential backoff on 429 and 5xx only. A 4xx other
than 429 is final: the request was wrong and retrying it would only produce the
same wrong request.

## What one run does not tell you

A single run is a sample. The assistants are stochastic even at low
temperature, and the retrieval behind each of them changes without notice. The
repository's claim is narrower than "which product is best": it is that on a
date, with a fixed prompt, an engine named these products. Trends need the
diff, and the diff needs at least two runs a week apart.

## Reproducibility limits worth stating

- Model ids move. `audit.py` records the model it called, and `AUDIT_*_MODEL`
  lets you pin one; a run on a different model is a different engine column
  even if the vendor is the same.
- Answers depend on the account's region and on any personalization the
  provider applies. Two people running this on the same day may not get the
  same text. The verbatim answer is stored for exactly that reason.
- The audit cannot see what an assistant answers to a logged-in enterprise
  tenant with private connectors — only the public answer surface.
