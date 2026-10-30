# Django Local AI Chatbot

A fully local, privacy-first AI chatbot.

- Backend: Django + Django REST Framework + SQLite
- Frontend: React + Vite
- AI: Ollama (local LLM + local embeddings)
- RAG: local vector storage in SQLite, retrievable citations
- Auth: Django sessions + CSRF

## One-click Docker install

Requirements: Docker Desktop.

```bash
docker compose up -d --build
```

Then open http://127.0.0.1:3010 and register. The API is on port 8010.

## Ubuntu server

Build here, then copy the images and the `deployment` folder. On the server, use only that folder (no Windows `C:/` mount).

```bash
docker compose build
docker save -o chatbot-images.tar chatbot-frontend:latest chatbot-backend:latest
scp chatbot-images.tar root@203.57.85.15:/root/tmp/
scp -r deployment root@203.57.85.15:/root/chatbot
```

You can also run `docker compose up -d --build` from this repo root on Ubuntu; the root `docker-compose.yml` is Linux-safe.

**Windows dev:** to expose the host `C:` drive inside the backend container for folder indexing, use:

```bash
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build
```

On the server:

```bash
cd /root/chatbot
bash start.sh
```

That starts the backend and the frontend and checks both. After HTTPS is installed, the site and the API are both on:

- https://vm24372508.manageserver.in/
- https://203.57.85.15/

Details are in [deployment/README.md](deployment/README.md).

Production, including the Cloudflare tunnel and the third-party button, is in [docs/hosting-and-embed.md](docs/hosting-and-embed.md).