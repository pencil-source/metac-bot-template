# One-time read-only API probe trigger

Purpose: test that the v0.3 question discovery script can read eligible
public tournament-style questions with the existing Metaculus bot token.

- Runs only one GitHub Actions GET-only workflow on the commit adding this marker.
- Zero OpenRouter calls, no Metaculus forecast submissions, no paid endpoints.
- Never edit this file again unless explicitly repeating the compatibility check.
- The GitHub Actions result records whether questions were available and a
  sanitized `question_snapshot.json` as an artifact (30 days).
