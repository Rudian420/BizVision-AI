#!/usr/bin/env bash
# BizVision AI — Staging deploy (Render API + Vercel).
# Placeholder pending Phase 6 (OPS-003). Fails loudly if creds are missing.
set -euo pipefail

echo "==> Deploying BizVision AI to STAGING"

: "${RENDER_API_KEY:?Set RENDER_API_KEY}"
: "${VERCEL_TOKEN:?Set VERCEL_TOKEN}"

echo "[staging] Building images..."
docker compose build backend frontend

echo "[staging] (TODO Phase 6) push backend image to Render and trigger deploy"
echo "[staging] (TODO Phase 6) deploy frontend to Vercel: vercel deploy --prod --token \$VERCEL_TOKEN"

echo "==> Staging deploy script finished (scaffold)."
