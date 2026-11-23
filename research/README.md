# Forecast audit: safe offline research (v0.1)

This folder is a **research-only evaluator**, not a prediction AI. It cannot submit
forecasts or access Metaculus. It uses only Python standard-library modules.

## How to run

From repository root, with Python 3.11+:

```bash
python -m unittest discover -s research -p "test_*.py" -v
python research/forecast_audit.py research/data/SYNTHETIC_EXAMPLE.csv
python research/forecast_audit.py your_predictions.csv --out audit.md
```

The sample data is **entirely synthetic**, not evidence of actual model performance.

## Data schema

```text
question_id,forecast_at,resolved_at,prediction,baseline,outcome,model_version,cost_usd
```

- Timestamps MUST include an offset (`2026-11-01T08:00:00+09:00`).
- Probabilities are decimals between 0 and 1.
- Leave both resolved_at and outcome empty until the outcome is verified.
- Fix the model and baseline probabilities **before** the answer is known.
- One recorded prediction per question/version; duplicate records error.
- Fail fast on any forecast timestamp at or after resolution. This does not detect earlier news leaks.

## Evaluation

Reports Brier score, log loss and paired naive bootstrap confidence intervals
versus a fixed baseline. The optional exploratory gate (100 independent resolved
forward predictions and positive confidence interval lower bound) is **not**
the official tournament scoring method. Correlated question clusters invalidate
the naive confidence interval. There is no claim of profits or prize competitiveness.

## Safety / costs

No API tokens, account credentials, network calls, paid services, or live
submission is required. The existing upstream GitHub workflows are
**not modified** by this research branch. In particular, do **not**
enable the upstream recurring workflow until credentials, usage caps,
competition requirements and costs are checked.

Official upstream: https://github.com/Metaculus/metac-bot-template
