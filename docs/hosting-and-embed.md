# Host the chatbot and add it to another website

The chatbot runs here. Another website only needs a short snippet. Visitors stay on that website; the chat opens there and talks to this app.

Two ways to add it:

- **Button.** A round button sits at the bottom right. A click opens the chat on that page.
- **Iframe.** The chat box itself is placed where you want it.

Both use the same chatbot id. Answers come from that account’s uploaded documents and database records.

## 1. Production command

Requirements: Docker Desktop.

From the project folder, the first time:

```bash
docker compose up -d --build
```

After that, and whenever `.env` changes:

```bash
docker compose up -d
```

`docker restart` does not reload `.env`. Compose reads `.env` when it creates the containers. The file stays on the host and is not copied into the frontend image, the backend image, or the Cloudflare image.

| Address | Port |
| --- | --- |
| Website | http://127.0.0.1:3010 |
| API | http://127.0.0.1:8010 |
| Ollama | stays on this machine only, port 11434 |

Open http://127.0.0.1:3010, register, and sign in. The website calls `/api` on the same address. Port 8010 is the API by itself.

Two env files, both outside the images:

- `.env` next to `docker-compose.yml` holds `UI_PORT`, `API_PORT`, and `TUNNEL_TOKEN`. Change the token or the ports here, then run `docker compose up -d`.
- `backend/.env` is mounted into the API container. Model keys and allowed hosts live here. Change that file, then run `docker compose restart backend`. No image rebuild.

## 2. Cloudflare tunnel

The compose file starts `cloudflare/cloudflared` with:

```text
tunnel --no-autoupdate run --token
```

The token value comes from `TUNNEL_TOKEN` in the host `.env`.

In the Cloudflare Zero Trust tunnel, set the public hostname service to:

```text
http://frontend:80
```

That is the website inside Docker. It also serves `/api`. Use a second hostname only if you want the API alone:

```text
http://backend:8000
```

If the dashboard is already pointed at this computer’s published ports, use `http://host.docker.internal:3010` for the website and `http://host.docker.internal:8010` for the API.

HTTPS is provided by Cloudflare. The other website must use that `https://` address in the script or iframe.

Django rejects a hostname it has not been given. In `backend/.env` add the public hostname and the `https` origin, and keep `backend` in the host list:

```env
DJANGO_ALLOWED_HOSTS=chat.example.com,127.0.0.1,localhost,backend
CORS_ALLOWED_ORIGINS=https://chat.example.com,http://127.0.0.1:3010,http://localhost:3010
CSRF_TRUSTED_ORIGINS=https://chat.example.com,http://127.0.0.1:3010,http://localhost:3010
```

Then:

```bash
docker compose restart backend
```

Sign in at the public `https://` address before you copy the embed snippet. The Embed screen uses the address in the browser bar.

## 2b. HTTPS on Ubuntu 24.04

The server copy is the `deployment` folder. It runs the backend and the frontend together, and the website on port 3010 already proxies `/api`. Steps, env files, and the SSL scripts are in [deployment/README.md](../deployment/README.md).

On the server, after `bash start.sh`:

```bash
sudo bash install_ssl.sh
sudo bash configure_ssl.sh you@example.com
docker compose up -d
```

The site and `/api` are then on https://vm24372508.manageserver.in/ and https://203.57.85.15/. Use the hostname in the embed snippet.

## 3. Copy the snippet

1. Sign in at the public address.
2. Click **Embed** in the top bar.
3. Set the chatbot name, greeting, and quick replies (one reply per line). Save.
4. Copy either **Button for any website** or **Iframe**.

The chatbot id looks like `2c5654bd-067d-4946-9f5a-e0f90d9b3daf`. Anyone who has the id can open that bot, so share it only with sites that should see this account’s documents.

You can also build the URLs yourself. Replace the host and the id.

Preview (button on a blank page):

```text
https://chat.example.com/embed?bot=CHATBOT_ID
```

Chat box only:

```text
https://chat.example.com/embed?bot=CHATBOT_ID&mode=panel
```

## 4. Put the button on the other website

Paste this once, just before `</body>`, on every page that should show the button:

```html
<script src="https://chat.example.com/widget.js" data-bot="CHATBOT_ID"></script>
```

What the visitor gets:

- A round button fixed at the bottom right.
- A click opens a panel on that same page: header, Online status, greeting, quick replies, and a message box.
- Closing it returns to the button. The closed button does not cover the page.

The script reads `data-bot` and loads the chat from the same host as `widget.js`. Keep that host equal to the public chatbot address.

A full page on the other site:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Our site</title>
  </head>
  <body>
    <h1>Welcome</h1>
    <p>The chat button is in the corner.</p>

    <script src="https://chat.example.com/widget.js" data-bot="CHATBOT_ID"></script>
  </body>
</html>
```

## 5. Or place the chat box with an iframe

Use this when the chat should sit in the page layout instead of floating over it:

```html
<iframe
  src="https://chat.example.com/embed?bot=CHATBOT_ID&mode=panel"
  title="Chat"
  style="width:380px;height:640px;border:0;border-radius:18px;"
></iframe>
```

`mode=panel` fills the frame with the open chat and hides the round button. `380` by `640` matches the panel size. The app already sends `Content-Security-Policy: frame-ancestors *`, so other sites are allowed to frame it.

## 6. Check that it works

On the other website:

1. The button appears at the bottom right, or the iframe shows the greeting.
2. A quick reply or a typed question returns an answer from the uploaded documents or database rows.
3. The browser address of the script or iframe is the public chatbot host, and it uses `https` when the other site does.

The Embed page on this app is the same widget: open `/embed?bot=CHATBOT_ID` and send a question there first. If that page works, the snippet on the other site uses the same chat.

## Troubleshooting

| What you see | What to change |
| --- | --- |
| Button never appears | The script tag is missing, `data-bot` is empty, or the chatbot host did not load. In the browser network tab, `widget.js` must be status 200. |
| Blank iframe or “Chatbot not found” | The id is wrong, or the bot was removed. Copy the id again from **Embed**. |
| `DisallowedHost` or the API returns 400 | Add the public hostname to `DJANGO_ALLOWED_HOSTS` in the `.env` file beside `docker-compose.yml`, then run `docker compose up -d`. |
| Console says mixed content | The other site is HTTPS and the snippet is still `http://`. Use the `https://` address. |
| Chat loads here but not from another computer | Use the Cloudflare hostname, or open port 3010. The tunnel service URL must be `http://frontend:80` or `http://host.docker.internal:3010`. |
| Answer says it could not find that | The signed-in account has no matching document or database row. Upload the file, or add the row, then ask again. |
| First answer is slow | The model call can take a while. The web proxy waits up to 5 minutes. |
