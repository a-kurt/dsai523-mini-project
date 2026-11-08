# Validation results

Checked on 8 November 2026 in the managed development environment.
Branch: `feat/movie-court`. Live GCP deployment has not been performed.

## Passed

- Reusable dependency setup: `python3 -m venv .venv`, followed by
  `.venv/bin/python -m pip install -r requirements-dev.txt`.
- SQLite: `.venv/bin/python -m pytest -q`: **21 passed, 2 skipped**.
  The skips are explicitly PostgreSQL-only concurrency checks.
- PostgreSQL 16: the same suite with `TEST_DATABASE_URL` targeting an isolated
  Docker database: **23 passed**, including all seven independent review tests.
  The tests exercise CRUD, status codes, role checks, CSRF, exact passwords,
  private cases, hidden ballots, expired/revoked/reused invitations, and upstream
  errors. Concurrent requests could redeem a token only once and cast only one
  vote for a juror. Tests create and drop tables; use a disposable database only.
- Chromium browser: `PYTHON=.venv/bin/python node scripts/browser_smoke.cjs`:
  registration, movie search, case creation/edit, three role invitations,
  argument creation/edit, safe text rendering, private voting, verdict, logout,
  and mobile overflow check passed. Screenshots were visually inspected.
  The real Flask app and database ran; **TMDB HTTP responses were fixtures**.
  Unique readiness checks prevent this test from acting on another app instance.
- Docker: image build passed with verified TLS and the optional proxy CA mount.
  Application runtime user is UID 999, not root.
- Docker Compose: app and PostgreSQL both healthy. HTTP checks confirmed account
  registration, authenticated API access, and the expected 503 when TMDB is not
  configured. After restarting the app, a fresh login succeeded using the same
  PostgreSQL account, demonstrating local persistence. The test account was removed.
- Python dependency consistency, JavaScript syntax, shell syntax, Compose
  configuration, and `git diff --check` passed.
- Independent review finished; all blocking findings were fixed. Review caught
  Unicode CSRF errors, a SQLite timestamp comparison, password whitespace loss,
  expired-session recovery, and browser fixture isolation. Regression tests remain.

## Local runtime and files

The app and PostgreSQL are running through Docker Compose. Their processes do
not survive a published snapshot. Startup instructions are saved separately.
The ignored `.env` contains generated local secrets, not production credentials.
It and the database volume must be preserved; no secrets were added to source.

GitHub Actions configuration runs both database suites and an image build.
It has been prepared, but no remote GitHub Actions execution is claimed.

## Live cloud checks still blocked

The user selected GCP project ID `movie-court`. No usable GCP identity was
connected: the injected credentials file was empty and identity metadata listed
no connections. The project, billing, and IAM access could not be verified.
Google Cloud CLI is installed in `/workspace/tools/google-cloud-sdk`.

No TMDB Read Access Token was present. Therefore no live TMDB result is claimed.
The production app intentionally returns an error when that token is absent.
The footer contains the TMDB disclaimer and link. Downloading the approved logo
was blocked by HTTP 403; add the official asset before public release after
network access is applied. Do not invent or redraw the TMDB logo.

The environment draft saves installation/startup instructions, project/region
suggestions, TMDB credential requirements, and TMDB/GCP network destinations.
These are saved proposals, not applied runtime access or a published snapshot.
Review and save them in environment settings, add the token securely, connect a
GCP identity, and publish when appropriate. Never paste secrets into chat.

Follow GCP.md to create Cloud SQL and Secret Manager values and deploy Cloud Run.
Then verify real search, full courtroom behavior, HTTPS/Secure cookies, and case
persistence across a new Cloud Run revision. **Local PostgreSQL is not proof of
an external cloud database.** No GCP service or cloud database has been created
or billed by this task.

## Course submission remains a team task

Confirm the fourth team member. Record the live demonstration with every member
appearing and explaining their contribution. Keep it within 15 minutes and open
with the required project/group/names/student IDs. Keep IDs out of public source.
Publish the source to the public repository and submit accessible repository and
video links through Moodle. The booklet lists 7 December 2026, 23:59; confirm its
timezone with the course. The rubric is covered by the implementation plan, but
cloud evidence and the actual presentation remain necessary for assessment.
