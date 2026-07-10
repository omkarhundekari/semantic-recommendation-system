# Sample LLM Synthesis Outputs

These files are curated test fixtures for the synthesis validator. They are not raw API logs.

`valid_synthesis_sample.json` is a sanitized example of a valid synthesis run. It is used to verify that the validator accepts well-formed output with valid source citations and no invented sources.

`invalid_truncated_sample.json` is a sanitized example of a truncated response. It is used to verify that the validator detects missing parsed responses and surfaces the correct warnings. This failure mode was observed during development when the output token budget was too low.

Real synthesis runs are saved locally to `outputs/llm_synthesis_runs/` and are not committed.
