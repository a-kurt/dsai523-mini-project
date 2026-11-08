# Deploy Movie Court on Google Cloud

This guide uses **Cloud Run + Cloud SQL for PostgreSQL**. The database is an
external cloud service, so it is suitable for the course's cloud persistence
requirement once the running application is demonstrated against it.

## Before you start

You need a GCP project with billing enabled, permission to create the services
below, the Google Cloud CLI, and a valid TMDB API Read Access Token. Select the
project yourself. Do not use another person's project or share credential JSON
files. Sign in through the normal Google Cloud CLI login flow on your own
computer, or use an already configured cloud identity.

**Cloud SQL, builds, storage, and traffic can cost money.** Cloud SQL continues
charging when Cloud Run scales to zero. Set a billing budget and alerts before
creating resources; budgets are alerts, not a hard spending cap. Use the smallest
suitable PostgreSQL instance and remove resources after assessment when no
longer needed. Cloud Run is capped at two instances by the deployment script.
Do not promise a free deployment or rely on free credits.

The current deployment target is project `movie-court-dsai523` in
`europe-west1`. Use the project explicitly when running deployment commands.

Use one region for Cloud Run, Artifact Registry, and Cloud SQL where possible.
The examples use `europe-west1`; choose the location suitable for your team.

## 1. Create the database and secrets

Use Google Cloud Console to create a PostgreSQL 16 Cloud SQL instance. Enable
its public IP for the built-in Cloud Run Cloud SQL connection. The connector
uses IAM and an encrypted connection; do not add `0.0.0.0/0` to authorized
networks. Keep backups enabled and set deletion protection for important data.

Create a database called `movie_court` and a dedicated built-in database user
called `movie_court` with a long random password. Give this user ownership or
CREATE permission on that database's `public` schema so `init-db` can create
tables. Do not use the default `postgres` account as the application account.
Use Cloud SQL Studio or an administrator connection to grant only the needed
schema permissions. For example, while connected to the `movie_court` database:

```sql
GRANT CONNECT ON DATABASE movie_court TO movie_court;
GRANT USAGE, CREATE ON SCHEMA public TO movie_court;
```

Do not expose SQL Studio sessions or database passwords in the demonstration.
Copy the instance's **connection name**, which looks like
`your-project:europe-west1:movie-court-db`.

Create three secrets in Secret Manager using its secure value entry UI:

| Suggested secret name | Value |
| --- | --- |
| `movie-court-database-url` | PostgreSQL URL below |
| `movie-court-session-key` | At least 32 random bytes, for example a 64-character random hex string |
| `movie-court-tmdb-token` | Your TMDB API Read Access Token |

The database URL must use the Cloud Run Unix socket:

```text
postgresql+psycopg://movie_court:URL_ENCODED_PASSWORD@/movie_court?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```

Replace placeholders privately. URL-encode special password characters; a
random hex password avoids that issue. Do not put actual secret values in this
file, shell history, source control, chat, build arguments, or command logs.
The deployment script references secret **names**, never values.

## 2. Deploy

From the repository root, set only non-secret configuration:

```sh
export PROJECT_ID=movie-court-dsai523
export REGION=europe-west1
export SQL_CONNECTION_NAME=movie-court-dsai523:europe-west1:movie-court-db
export DATABASE_SECRET=movie-court-database-url
export SESSION_SECRET=movie-court-session-key
export TMDB_SECRET=movie-court-tmdb-token
bash scripts/gcp-deploy.sh
```

The script:

1. Verifies the project and enables the required APIs.
2. Creates an Artifact Registry Docker repository if missing.
3. Creates a dedicated runtime service account and grants Cloud SQL Client.
4. Grants that account access to only the three named secrets.
5. Builds a uniquely tagged image with Cloud Build using `cloudbuild.yaml`.
   That configuration enables Docker BuildKit, required by the Dockerfile's
   optional build-secret mount.
6. Runs a one-task Cloud Run job to create missing database tables.
7. Deploys the image to Cloud Run with the SQL connection and secrets attached.
8. Checks the service's `/health` endpoint and prints its HTTPS address.

The person deploying needs suitable IAM permissions for those actions, including
permission to use the runtime service account. Cloud Build's build service
account needs Artifact Registry write access to the repository. If your
organization does not grant this by default, ask its administrator to grant
`roles/artifactregistry.writer` on this repository to the project's configured
Cloud Build service account. Avoid broad Owner grants as a shortcut.

The service allows unauthenticated access at the Cloud Run layer so visitors
can load the sign-in page. The application still requires sign-in and case
membership for private data. `APP_ENV=production` enables Secure cookies;
`TRUST_PROXY=1` trusts Cloud Run's forwarding headers. Do not set that flag on
an untrusted direct internet server.

## 3. Verify the real cloud workflow

A health response is only a startup check. Follow [DEMO.md](DEMO.md) with real
TMDB searches and at least four accounts. Confirm that:

- The site loads over HTTPS and session cookies are Secure and HttpOnly.
- Search returns real TMDB results; creating a case fetches real movie details.
- An outsider cannot access a case or vote. The judge cannot vote.
- Expired, revoked, and already-used invitation tokens are refused.
- Jurors can vote only once; totals are hidden until the judge closes voting.
- A new case and its arguments remain after a fresh Cloud Run revision starts.
- Cloud SQL contains the application's rows. Show this without exposing hashes,
  credentials, or personal information.

Record the deployed project, service, image tag, date, and actual results in
[VALIDATION.md](VALIDATION.md). A prepared script is not proof that these checks
passed. Local Docker PostgreSQL is not a substitute for this cloud evidence.

## Updates and schema changes

Rerun the deployment script to build and deploy a new image. It uses a distinct
tag and executes schema initialization first. `init-db` creates missing tables
only; it is **not** a migration engine and will not alter existing columns.
Before making schema changes, add and test a migration and take a backup.
Do not drop the database to repair a deployment error.

Secret references use `latest`; a newly started instance reads that version.
For controlled releases, pin the desired secret version in the deployment
script. Rotating the session secret signs existing users out. Rotate a database
password and the corresponding secret together, then redeploy. Never delete
an old version until the new revision has been validated.

## Troubleshooting

- **Google-branded 404 for `/healthz`:** use `/health` for public Cloud Run
  health checks. The legacy `/healthz` route remains available for direct local
  container checks, but Google's front end can intercept that path.

- **403 from GCP:** check the active identity, explicit project, API enablement,
  service account impersonation, and required IAM roles.
- **Database connection fails:** check the instance connection name, its state,
  public IP configuration, Cloud SQL Client role, attached connection, database,
  password encoding, and the URL's socket path.
- **Schema permission denied:** grant the dedicated user the database/schema
  permissions described above, then rerun the initialization job.
- **TMDB search fails:** check that the secret contains a Read Access Token and
  that outbound HTTPS to `api.themoviedb.org` is allowed. Do not disable TLS checks.
- **Sign-in does not persist locally:** production Secure cookies need HTTPS.
  Use development mode only for local HTTP.
- **Build upload contains local files:** inspect `.gcloudignore` before upload.
  Do not upload secrets even if the application would ignore them.

## Costs and cleanup

Cloud Run's zero minimum instances reduces idle compute, but Cloud SQL does
not scale to zero. Artifact Registry images, Cloud Build, backups, and network
traffic may add charges. Check Billing and each service after the demo.

After grading, decide which data to retain. Export/backup the database before
removal. In Console, delete only this project's Movie Court service, initialization
job, unused images/repository, database instance, secrets, and runtime service
account when they are no longer needed. Review dependencies first. No script
in this repository automatically deletes cloud resources or databases.
