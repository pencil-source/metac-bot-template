# One-time free history sync smoke test

Triggers exactly one read-only run on first creation.
Downloads prior GitHub forecast artifacts using the built-in GITHUB_TOKEN,
checks Metaculus resolution visibility via GET, and writes a score report.
No OpenRouter calls, paid API calls, Metaculus POST, or recurring schedule.
Do not edit this marker again unless deliberately re-testing.
