# Movie Court implementation plan

Build a Flask app with SQLAlchemy and PostgreSQL. SQLite is only for quick local tests.
Use a server-rendered shell and plain JavaScript. The same-origin JSON API uses a
secure HttpOnly session cookie and a CSRF token. Passwords use Werkzeug scrypt.
No custom cryptography. Jury invite tokens are random secrets; store SHA-256 hashes.

## API contract
All JSON responses use objects. Errors: {"error": "simple English message"}.
- GET /api/auth/me -> {user: {id, username} or null, csrf_token: string}
- POST /api/auth/register {username,password} -> {user} 201, signed in
- POST /api/auth/login {username,password} -> {user}
- POST /api/auth/logout -> 204
All mutation requests require X-CSRF-Token from /api/auth/me. Refresh me after login/register.
- GET /api/movies/search?q=... -> {movies:[{id,title,release_date,overview,poster_path}]}
- GET /api/cases -> {cases:[case summary]} authenticated member cases only
- POST /api/cases {movie_id, title, charge} -> {case} 201. Fetch real movie metadata server-side.
- GET /api/cases/<id> -> {case, members, arguments, verdict, my_role, my_vote}
- PATCH /api/cases/<id> {title,charge} -> {case}; judge only, before voting
- DELETE /api/cases/<id> -> 204; judge only
- POST /api/cases/<id>/invites {role: prosecutor|defender|juror} -> {token,expires_at} 201; judge only
- DELETE /api/cases/<id>/invites -> 204; judge revokes unused invites
- POST /api/invites/redeem {token} -> {case_id,role} 201; registered user, atomic single use
- POST /api/cases/<id>/arguments {body} -> {argument} 201; prosecutor/defender in debate
- PATCH /api/cases/<id>/arguments/<argument_id> {body} -> {argument}; own argument, debate
- DELETE /api/cases/<id>/arguments/<argument_id> -> 204; own argument, debate
- POST /api/cases/<id>/phase {phase: voting|closed} -> {case}; judge only, debate->voting->closed
- POST /api/cases/<id>/votes {choice: guilty|not_guilty} -> {message} 201; juror only, voting, once

Case fields: id, title, charge, phase (debate|voting|closed), movie (id,title,release_date,overview,poster_path), created_at.
Members: [{user_id,username,role}]. Arguments: [{id,user_id,username,role,body,created_at}].
verdict null until closed, then {guilty,not_guilty,total,result: guilty|not_guilty|tie|no_votes}.
my_vote null or choice; my_role judge|prosecutor|defender|juror.
No vote totals or other voters' choices exposed before close. Judge cannot vote.
Only one prosecutor and defender per case; any number of jurors. Must have both advocates and
at least one juror before voting. At least one vote before closing.

## Deployment and validation
Docker Compose: app + PostgreSQL. GCP: Cloud Run + Cloud SQL PostgreSQL + Secret Manager,
Artifact Registry. HTTPS managed by Cloud Run. No cloud readiness claim without live validation.
TMDB requires a read access token supplied securely; no invented live data. Mock it in tests.
Tests: functional API workflow, permissions, CSRF, expired/reused/revoked invites, hidden ballots,
upstream failures, database persistence. Browser smoke and Docker workflow.

## Course delivery
20 REST CRUD + 20 external REST + 20 external cloud DB + 10 documentation.
Security option: HTTPS + hash-based authentication + user accounts/access management (up to 30).
Custom invite token is an additional demonstration, not a guaranteed separate bonus.
Four team members; public GitHub; max 15-minute video; every member appears and presents.
Video opens with project/group/names/student IDs. Keep student IDs out of public source.
Deadline per booklet: 7 December 2026, 23:59. User must record and submit the video.

## Work allocation
Backend agent: Python app, dependency pins, auth, models, API, backend tests.
Frontend agent: templates, static assets, browser interface only.
Deployment agent: Docker, GCP deployment scripts, docs, README and AGENTS updates.
Lead: integration, environment setup, browser and Docker validation, credential diagnosis.
Independent reviewer: security, correctness, rubric gaps, regression tests; findings fixed before finish.
