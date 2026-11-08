# Validation results

Checked on 8 November 2026. Branch: `feat/movie-court`.

## Verified live deployment

- Live site: https://movie-court-776677100055.europe-west1.run.app
- GCP project: `movie-court-dsai523`; region: `europe-west1`.
- Cloud Run uses a non-root Docker image and Cloud SQL PostgreSQL 16
  (`movie-court-db`, `db-f1-micro`, 10 GiB disk). The runtime account has Cloud SQL
  Client and access to the three application secrets in Secret Manager.
- `/health` returned HTTP 200 and confirmed the database connection. Use this
  public endpoint: Google's front end can intercept the legacy `/healthz` path.
- The existing pytest suite exited successfully before the health-route fix was
  built and deployed. Cloud Build passed with Docker BuildKit enabled; the
  committed `cloudbuild.yaml` and deployment script now use that configuration.
- Live functional checks passed at **2026-11-08 18:46:21 UTC** using five
  independent user sessions and real TMDB responses:
  - registration over HTTPS and Secure/HttpOnly session cookies;
  - mutation without CSRF rejected;
  - real Shrek 2 search and server-side movie details;
  - non-members denied access;
  - separate prosecutor, defender, and juror invitations; reused token rejected;
  - advocate arguments, judge denied voting, juror allowed exactly one vote;
  - vote totals hidden until closing, then the correct verdict returned;
  - case, membership, arguments, verdict, and authenticated session persisted
    after creating and routing traffic to a fresh Cloud Run revision.
- The approved TMDB read token was stored privately in Secret Manager. No token,
  password, session cookie, or cloud credential was committed or printed.
- The official TMDB SVG was downloaded unchanged from its attribution page and
  included in the footer alongside the required disclaimer.

These checks verify deployment and the exercised workflow, not completion of the
team's presentation or every possible production scenario.

## Earlier managed-development checks

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

## Cloud environment configuration

The reusable environment has been republished with `PROJECT_ID=movie-court-dsai523`
and a keyless Google Cloud OIDC connection restricted to the configured connection
subject. Existing tasks can retain their older runtime state; new tasks should
use the latest published environment. The live deployment and validation above
ran in the authenticated Google Cloud Shell. Do not paste credentials into chat.

## Course submission remains a team task

Confirm the fourth team member. Record the live demonstration with every member
appearing and explaining their contribution. Keep it within 15 minutes and open
with the required project/group/names/student IDs. Keep IDs out of public source.
Publish the source to the public repository and submit accessible repository and
video links through Moodle. The booklet lists 7 December 2026, 23:59; confirm its
timezone with the course. The rubric is covered by the implementation plan, but
the actual presentation and the team's course submission remain necessary for assessment.
