# Server deployment (Ubuntu 24.04)

This folder runs on the Ubuntu server. It starts the backend and the frontend from images that were already built. It does not build them, and it does not mount a Windows drive.

The frontend container serves the website and forwards `/api` to the backend container. Both have to be running. `nginx.conf` is mounted into the frontend and calls the backend service by the hostname `backend`.

| Check | Address |
| --- | --- |
| Website | https://vm24372508.manageserver.in/ |
| Same site by IP | https://203.57.85.15/ |
| API through the website | https://vm24372508.manageserver.in/api/system/health/ |
| API through the IP | https://203.57.85.15/api/system/health/ |
| API on the server only | http://127.0.0.1:8010/api/system/health/ |

A healthy API returns `{"status": "ok"}`.

## 1. Build the images on the machine that has the source

From the project root (the folder that contains the Windows `docker-compose.yml`):

```bash
docker compose build
docker save -o chatbotfrontendlatest.tar chatbot-frontend:latest chatbot-backend:latest
```

Copy the tar and this folder to the server:

```bash
scp chatbotfrontendlatest.tar root@203.57.85.15:/root/tmp/
scp -r deployment root@203.57.85.15:/root/chatbot
```

## 2. Start both containers

On the server:

```bash
cd /root/chatbot
bash start.sh
```

`start.sh` loads `/root/tmp/chatbotfrontendlatest.tar` when that file is present, then runs `docker compose up -d`. It waits until all three checks pass:

- backend health on port 8010
- the website on port 3010
- `/api/system/health/` on port 3010, which is the frontend reaching the backend

Open http://203.57.85.15:3010 and register. After the HTTPS step below, use the `https://` addresses instead.

After you load a **new** backend image (new app migrations), apply them once:

```bash
cd /root/chatbot
docker compose exec backend python manage.py migrate --noinput
docker compose restart backend
```

Migrations also run when the backend container is recreated from an image whose `entrypoint.sh` includes `migrate`. Check status with:

```bash
docker compose exec backend python manage.py showmigrations chatbot
```

`backend/.env` already allows `vm24372508.manageserver.in` and `203.57.85.15` for login.

After editing `backend/.env`:

```bash
docker compose up -d
```

`docker restart` does not reload that file. Compose reads it when it recreates the backend container.

## 3. HTTPS

`vm24372508.manageserver.in` must point at `203.57.85.15`. Port 80 and port 443 must be open. The containers must already be up.

```bash
sudo bash install_ssl.sh
sudo bash configure_ssl.sh you@example.com
docker compose up -d
```

Replace `you@example.com` with a real address. Certbot uses it for expiry notices.

Nginx on the host answers both names on port 443 and forwards every path to the frontend on port 3010. The frontend serves the website and forwards `/api` to the backend, so these are the same app:

- https://vm24372508.manageserver.in/
- https://vm24372508.manageserver.in/api/system/health/
- https://203.57.85.15/
- https://203.57.85.15/api/system/health/

A healthy API returns `{"status": "ok"}`. `backend/.env` already trusts both `https://` origins.

The certificate that includes the IP lasts about 6 days. The Certbot timer renews it. Rebuild and copy the images again after this change so the frontend keeps the HTTPS scheme when it calls the backend.

## Files

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Backend and frontend, shared network, health checks |
| `nginx.conf` | Frontend proxy. Mounted over the image so `/api` can resolve `backend` |
| `.env` | `UI_PORT` and `API_PORT` |
| `backend/.env` | Hosts, CSRF, and the model settings mounted into the API |
| `approved_folders/` | Folder index root inside the backend |
| `start.sh` | Load the tar, start both, check both |
| `install_ssl.sh` | Nginx and Certbot on Ubuntu 24.04 |
| `configure_ssl.sh` | Certificate and HTTPS proxy to port 3010 |

Do not use the compose file from the project root on this server. That file mounts `C:/` and builds from source.
