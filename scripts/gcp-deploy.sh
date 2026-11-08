#!/usr/bin/env bash
# Build, create the schema, and deploy an existing GCP database + secrets.
# This script creates billable resources. Read docs/GCP.md first.
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID explicitly}"
: "${REGION:?Set REGION explicitly, for example europe-west1}"
: "${SQL_CONNECTION_NAME:?Set project:region:instance for an existing Cloud SQL instance}"
: "${DATABASE_SECRET:?Set Secret Manager name containing DATABASE_URL}"
: "${SESSION_SECRET:?Set Secret Manager name containing SECRET_KEY}"
: "${TMDB_SECRET:?Set Secret Manager name containing TMDB_READ_TOKEN}"
SERVICE_NAME=${SERVICE_NAME:-movie-court}
REPOSITORY=${REPOSITORY:-movie-court}
SA_NAME=${SA_NAME:-movie-court}
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
TAG=$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/app:$TAG"
command -v gcloud >/dev/null || { echo 'Install the Google Cloud CLI first.' >&2; exit 1; }
gcloud projects describe "$PROJECT_ID" --format='value(projectId)' >/dev/null
# Do not print secret contents or enable shell tracing.
gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com --project "$PROJECT_ID" --quiet
if ! gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" --repository-format docker --location "$REGION" --project "$PROJECT_ID" --quiet
fi
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name 'Movie Court runtime' --project "$PROJECT_ID" --quiet
fi
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA_EMAIL" --role roles/cloudsql.client --condition=None --quiet >/dev/null
for secret in "$DATABASE_SECRET" "$SESSION_SECRET" "$TMDB_SECRET"; do
  gcloud secrets describe "$secret" --project "$PROJECT_ID" >/dev/null
  gcloud secrets add-iam-policy-binding "$secret" --member "serviceAccount:$SA_EMAIL" --role roles/secretmanager.secretAccessor --quiet >/dev/null
done
# Use .gcloudignore so local credentials and generated files are never uploaded.
gcloud builds submit . --config cloudbuild.yaml --substitutions "_IMAGE=$IMAGE" --project "$PROJECT_ID" --quiet
SECRETS="DATABASE_URL=$DATABASE_SECRET:latest,SECRET_KEY=$SESSION_SECRET:latest,TMDB_READ_TOKEN=$TMDB_SECRET:latest"
gcloud run jobs deploy "$SERVICE_NAME-init" --image "$IMAGE" --region "$REGION" --project "$PROJECT_ID" \
  --service-account "$SA_EMAIL" --set-cloudsql-instances "$SQL_CONNECTION_NAME" \
  --set-secrets "$SECRETS" --set-env-vars 'APP_ENV=production,TRUST_PROXY=1' \
  --command flask --args=--app,movie_court,init-db --tasks 1 --max-retries 0 --quiet
gcloud run jobs execute "$SERVICE_NAME-init" --wait --region "$REGION" --project "$PROJECT_ID" --quiet
gcloud run deploy "$SERVICE_NAME" --image "$IMAGE" --region "$REGION" --project "$PROJECT_ID" \
  --service-account "$SA_EMAIL" --add-cloudsql-instances "$SQL_CONNECTION_NAME" \
  --set-secrets "$SECRETS" --set-env-vars 'APP_ENV=production,TRUST_PROXY=1' \
  --port 8080 --memory 512Mi --cpu 1 --concurrency 20 --min-instances 0 --max-instances 2 \
  --allow-unauthenticated --quiet
URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
curl --fail --silent --show-error --max-time 30 "$URL/healthz"
printf '\nOpen %s and follow docs/DEMO.md to validate the live workflow.\n' "$URL"
