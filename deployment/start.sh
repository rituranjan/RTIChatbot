#!/usr/bin/env bash
# Load the image tar if it is present, start backend and frontend, then check both.
# Run on the Ubuntu server from this folder: bash start.sh
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi
if [[ ! -f backend/.env && -f backend/.env.example ]]; then
  cp backend/.env.example backend/.env
fi
mkdir -p approved_folders

TAR=""
if [[ -f ./chatbotfrontendlatest.tar ]]; then
  TAR="./chatbotfrontendlatest.tar"
elif [[ -f /root/tmp/chatbotfrontendlatest.tar ]]; then
  TAR="/root/tmp/chatbotfrontendlatest.tar"
fi

if [[ -n "${TAR}" ]]; then
  echo "Loading images from ${TAR}"
  docker load -i "${TAR}"
  RECREATE=(--force-recreate)
else
  RECREATE=()
fi

if ! docker image inspect chatbot-backend:latest >/dev/null 2>&1; then
  echo "Missing image chatbot-backend:latest. Load the tar before starting." >&2
  exit 1
fi
if ! docker image inspect chatbot-frontend:latest >/dev/null 2>&1; then
  echo "Missing image chatbot-frontend:latest. Load the tar before starting." >&2
  exit 1
fi

docker compose up -d "${RECREATE[@]}"

UI_PORT=3010
API_PORT=8010
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

echo "Waiting for backend :${API_PORT} and frontend :${UI_PORT}"
ok=0
for _ in $(seq 1 40); do
  backend_ok=0
  frontend_page_ok=0
  frontend_api_ok=0
  curl -fsS "http://127.0.0.1:${API_PORT}/api/system/health/" >/dev/null 2>&1 && backend_ok=1
  curl -fsS -o /dev/null "http://127.0.0.1:${UI_PORT}/" 2>/dev/null && frontend_page_ok=1
  curl -fsS "http://127.0.0.1:${UI_PORT}/api/system/health/" >/dev/null 2>&1 && frontend_api_ok=1
  if [[ "${backend_ok}" -eq 1 && "${frontend_page_ok}" -eq 1 && "${frontend_api_ok}" -eq 1 ]]; then
    ok=1
    break
  fi
  sleep 3
done

docker compose ps

if [[ "${ok}" -ne 1 ]]; then
  echo "Backend or frontend did not answer. Recent logs:" >&2
  docker compose logs --tail 60
  exit 1
fi

echo
echo "Backend is up:  http://127.0.0.1:${API_PORT}/api/system/health/"
echo "Frontend is up: http://127.0.0.1:${UI_PORT}/"
echo "API via the site: http://127.0.0.1:${UI_PORT}/api/system/health/"
