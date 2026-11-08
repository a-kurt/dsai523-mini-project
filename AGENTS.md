# Project context

Movie Court is the DSAI 523 Cloud Computing and Distributed Systems mini-project.
Read README.md and docs/IMPLEMENTATION_PLAN.md before changing it.

## Architecture and requirements

- Python 3.12 + Flask JSON API with a same-origin plain JavaScript UI.
- PostgreSQL on GCP Cloud SQL is the production database; SQLite is local/test only.
- GCP Cloud Run runs the Docker image. Keep the runtime non-root.
- TMDB movie search/details are real external REST calls. Mock them in automated tests.
- Security bonus: HTTPS + scrypt password hashing + user accounts/access management.
- Custom invitation tokens are random, expiring, single use, revocable, and stored as hashes.
- A case has a judge, one prosecutor, one defender, and jurors. Enforce membership
  and role checks on the server. Only jurors vote, once, and totals stay hidden until close.
- All mutating browser requests require CSRF protection. Keep cookies HttpOnly and
  secure on HTTPS. Do not implement custom cryptography or expose credentials.
- Store all new secret names as placeholders in .env.example; never commit real values,
  cloud credential files, student IDs, or private contact details.

## Development

Use the current checkout; each cloud task is already isolated. Do not create a
Git worktree unless the user requests it. Follow the branch/PR review workflow.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Full local stack: `docker compose up --build -d` after filling the ignored `.env`.
Health check: `curl --fail http://127.0.0.1:8080/healthz`.
Initialize schema explicitly with `flask --app movie_court init-db`. It creates
missing tables; it does not migrate existing schemas. Plan a migration before
changing deployed database structure.

## Validation and documentation

Run relevant functional tests for permissions, lifecycle, tokens, votes, CSRF,
and upstream failures. Run a browser flow when changing the UI. Test Docker and
PostgreSQL when changing packaging or database behavior. Preserve TLS verification.
Do not call a command verified until it has executed successfully. Record current
checks and cloud blockers in docs/VALIDATION.md. No local database proves GCP readiness.
Update API/setup/demo docs when behavior changes. Use simple English in UI and docs.

## Course delivery

Keep the scope small enough for four students to explain. The 15-minute maximum
video must include a live demonstration and every member's own contribution.
IDs belong in the private presentation, not the public repository. Any bonus
outside the documented options requires instructor preapproval.
