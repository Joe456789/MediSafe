#!/usr/bin/env bash
# Redeploys the MediSafe Cloud Run service from local source.
#
# Always includes the GCS FUSE volume mount at backend/data/ so reminders,
# reports, profiles, and family links survive Cloud Run's scale-to-zero /
# instance recycling (local container disk is NOT persistent between
# instances -- this bit us once already, see git log).
#
# Usage: bash scripts/redeploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

: "${GCP_PROJECT_ID:?Missing GCP_PROJECT_ID in .env}"
: "${GCP_REGION:?Missing GCP_REGION in .env}"
: "${SERVICE_NAME:?Missing SERVICE_NAME in .env}"
: "${GEMINI_API_KEY:?Missing GEMINI_API_KEY in .env}"
: "${LINE_CHANNEL_ACCESS_TOKEN:?Missing LINE_CHANNEL_ACCESS_TOKEN in .env}"
: "${LINE_CHANNEL_SECRET:?Missing LINE_CHANNEL_SECRET in .env}"
: "${LIFF_REPORT_URL:?Missing LIFF_REPORT_URL in .env}"
: "${LIFF_PROFILE_URL:?Missing LIFF_PROFILE_URL in .env}"

DATA_BUCKET="${MEDISAFE_DATA_BUCKET:-medisafe-line-2026-data}"

# MSYS2_ARG_CONV_EXCL stops Git Bash on Windows from mangling the unix
# absolute mount-path into a Windows path (e.g. C:/Program Files/Git/app/...).
MSYS2_ARG_CONV_EXCL="--add-volume-mount=" gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --execution-environment=gen2 \
  --add-volume=name=data,type=cloud-storage,bucket="$DATA_BUCKET" \
  --add-volume-mount=volume=data,mount-path=/app/backend/data \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},LINE_CHANNEL_ACCESS_TOKEN=${LINE_CHANNEL_ACCESS_TOKEN},LINE_CHANNEL_SECRET=${LINE_CHANNEL_SECRET},LIFF_REPORT_URL=${LIFF_REPORT_URL},LIFF_PROFILE_URL=${LIFF_PROFILE_URL}"
