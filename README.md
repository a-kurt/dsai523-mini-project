# Movie Court ⚖️

Put a movie on trial. Is *Shrek 2* the greatest sequel ever? Open a case, invite
friends as prosecutor, defender, and jurors, hear the arguments, then reveal the
verdict. This is the DSAI 523 Cloud Computing and Distributed Systems mini-project.

## How it works

1. Create an account and search for a movie through TMDB.
2. Open a case with a title and a clear charge. You become its judge.
3. Generate a separate invitation for the prosecutor, defender, and each juror.
4. Friends sign in and redeem their tokens. Both advocates post arguments.
5. The judge starts voting. Each juror casts one private, final ballot.
6. The judge closes the case. Everyone in the case can see the totals and verdict.

Only case members can read a case. A judge cannot vote. Arguments stop when voting
starts. A token can be used once, expires, and can be revoked. The server stores
its hash, not the raw token. This is an invitation system, not custom encryption.

## Stack

- Python 3.12, Flask, SQLAlchemy, Gunicorn, plain JavaScript and CSS.
- PostgreSQL in Docker for local development.
- GCP Cloud Run, Cloud SQL for PostgreSQL, Artifact Registry, and Secret Manager.
- TMDB REST API for movie search and details. A TMDB API Read Access Token is required.
- HTTPS on Cloud Run, scrypt password hashes, HttpOnly sessions, CSRF protection,
  and case roles cover the selected security bonus route.

## Run locally with Docker

Install Docker with Compose. From this repository:

```sh
cp .env.example .env
python -c 'import secrets; print(secrets.token_hex(32))'
```

Put a generated value in `SECRET_KEY` and a different generated value in
`POSTGRES_PASSWORD`. Use hex characters for the database password so it is safe
in the connection URL. Put your TMDB **API Read Access Token** in `TMDB_READ_TOKEN`.
Get it from your TMDB account's API settings. Do not use a shorter v3 API key here.
Never commit `.env` or paste credentials into an issue or chat.

```sh
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8080/healthz
```

Open `http://127.0.0.1:8080` in your local browser. Compose waits for PostgreSQL,
creates missing tables, and starts the app. Its database volume survives
`docker compose down`. Existing databases do not change their password just
because `.env` changes. Keep the original password or update the database user
through PostgreSQL; do not remove the volume to work around this.

```sh
docker compose logs --tail=100 app
docker compose down
```

`docker compose down --volumes` permanently deletes local data. Use it only when
you intentionally want to discard the development database.

The app can start without TMDB configured, but search and case creation cannot
work until a valid token is supplied. It never replaces failed API responses
with fake movie data.

## Run Python and tests

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

For a quick local app without Docker, set `SECRET_KEY` to a random secret and
`TMDB_READ_TOKEN` in your shell, then:

```sh
export DATABASE_URL=sqlite:///movie_court.sqlite3
flask --app movie_court init-db
flask --app movie_court run --host 127.0.0.1 --port 8080
```

SQLite is a local convenience. It does **not** fulfill the cloud database course
requirement. Direct Python commands do not automatically load `.env`; export
variables yourself without printing credentials. The development server is for
local work only. Automated tests mock TMDB so they do not need real credentials.

## Browser and PostgreSQL checks

Run the same API tests against a **disposable** PostgreSQL database by setting
`TEST_DATABASE_URL` before `python -m pytest -q`. The tests create and drop tables.
Never point that variable at a development or production database with useful data.
The two PostgreSQL-only tests check simultaneous token redemption and voting.

The browser smoke test uses real Flask endpoints and a temporary SQLite database.
Only the TMDB HTTP responses are test fixtures. Install Playwright outside the
repository if it is not already available:

```sh
npm install --prefix /tmp/movie-court-browser playwright@1.56.1
NODE_PATH=/tmp/movie-court-browser/node_modules PYTHON=.venv/bin/python node scripts/browser_smoke.cjs
```

The script uses `/usr/bin/chromium` by default. Set `BROWSER_BIN` if Chromium is
installed elsewhere. Screenshots go to `/tmp/movie-court-browser-artifacts`.
It does not validate live TMDB access or GCP deployment.

In this managed coding environment only, use the proxy CA override so Docker
builds and TMDB requests keep TLS verification enabled:

```sh
docker compose -f compose.yaml -f compose.managed.yaml up --build -d --wait
```

The override mounts the current public CA bundle read-only. Do not copy it into
an image or disable certificate checks. Ordinary local Docker and GCP use the
normal `compose.yaml` or deployment script.

## Documentation

- [API reference](docs/API.md): requests, responses, permissions, and errors.
- [GCP deployment](docs/GCP.md): services, secrets, database setup, deployment, and costs.
- [Demo guide and rubric](docs/DEMO.md): evidence to show and a four-person video plan.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): architecture and API decisions.

Deployment scripts are preparation, not evidence of a live deployment. Read
[validation status](docs/VALIDATION.md) for checks that actually ran and remaining
external requirements. A cloud database must be verified on GCP before claiming
that course requirement is complete.

## Team and submission

- Atakan Kurt (GitHub: @a-kurt)
- Ozan Çolak (GitHub: @ozancolak01)
- Berry (GitHub: @xemeriusss)
- Fourth team member: to be confirmed

The booklet requires **exactly four members**, a publicly accessible GitHub
repository, and a video of **at most 15 minutes** in which every member appears
and explains their contribution. Open the video with the project name, group
number, full names, and student IDs. Keep IDs out of this public repository.
Submit only the repository and video links on Moodle by **7 December 2026,
23:59**, as written in the booklet. YouTube satisfies both documents' platform
instructions. Confirm the deadline's timezone with the course.

The detailed rubric gives 20 points for REST CRUD, 20 for an external REST API,
20 for a cloud database, 10 for documentation, and up to 30 for a bonus option.
We use Option 2: HTTPS, hash-based authentication, and user accounts/access
management. Custom invitation tokens support the application; the documents do
not name them as a separate automatic bonus. Grades are the instructor's decision.

Use a branch for each change and ask a teammate to review the pull request before
merging. Every member should understand and be able to explain their contribution.

## TMDB attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.
Movie metadata comes from [The Movie Database](https://www.themoviedb.org/).
