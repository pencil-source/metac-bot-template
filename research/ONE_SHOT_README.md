# One free binary forecast — research dry-run

This is a **one-question experiment**, not a validated forecasting model. It has no web research and cannot post to Metaculus. It uses only a pinned OpenRouter free model and makes at most one request each time you manually run it.

## How to use

Open GitHub Actions > **One free binary forecast (dry-run only)** > Run workflow. You can leave the default question or enter a public yes/no forecasting question with an explicit horizon. The result is shown under the workflow run **Summary** and in its job log.

**Public repository warning:** workflow inputs, question text, probabilities and rationale may be publicly visible. Never enter API keys, private details or other sensitive information into the question field.

## Cost and reliability

- The model is pinned to `nvidia/nemotron-3.5-super-vl:free` based on the successful first forecast. If the model becomes unavailable, the job fails rather than switching models.
- The API key is read from the GitHub Actions secret `OPENROUTER_API_KEY`.
- No paid fallback, recurring schedule, or access to the Metaculus token.
- The provider-reported usage cost appears in the report when present; a missing value is not proof of zero charges.
- If the model fails to emit valid JSON, the job fails rather than inventing a probability.

Only after many **pre-outcome timestamped forecasts** resolve, compare proper scores (e.g. Brier loss) against a fixed baseline. This single run does not establish prediction quality or income potential.

The official tournament workflows are separately guarded by `PENCIL_LIVE_ENABLED` and should remain disabled during experiments.

Each successful new run uploads `forecast_record.json` to the run's Artifacts section (90-day retention). It records the original question, exact served model, baseline 0.5, predicted YES probability and timestamp before the answer is known. Download and preserve forecast records before expiry. Resolution/outcome remains blank until independently verified. For fair comparisons, use new questions that resolve within a few weeks, not a multi-year horizon.
