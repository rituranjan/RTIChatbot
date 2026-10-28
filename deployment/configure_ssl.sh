#!/usr/bin/env bash
# HTTPS for the hostname and the IP. The website and /api both use this proxy.
# Ubuntu 24.04. Containers must already be listening on port 3010.
#
#   sudo bash configure_ssl.sh you@example.com
#   sudo bash configure_ssl.sh vm24372508.manageserver.in you@example.com
#   sudo bash configure_ssl.sh vm24372508.manageserver.in you@example.com 203.57.85.15 3010
set -euo pipefail

DEFAULT_DOMAIN="vm24372508.manageserver.in"
DEFAULT_IP="203.57.85.15"
SITE_NAME="chatbot"
SITE_PATH="/etc/nginx/sites-available/${SITE_NAME}"
WEBROOT="/var/www/certbot"
CERTBOT="${CERTBOT:-/snap/bin/certbot}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash configure_ssl.sh you@example.com" >&2
  exit 1
fi

if [[ "${1:-}" == *@* && -z "${2:-}" ]]; then
  EMAIL="$1"
  DOMAIN="$DEFAULT_DOMAIN"
  IP="$DEFAULT_IP"
  UPSTREAM_PORT="3010"
elif [[ "${1:-}" == *@* ]]; then
  EMAIL="$1"
  DOMAIN="$DEFAULT_DOMAIN"
  IP="$DEFAULT_IP"
  UPSTREAM_PORT="${2:-3010}"
else
  DOMAIN="${1:-$DEFAULT_DOMAIN}"
  EMAIL="${2:-}"
  IP="${3:-$DEFAULT_IP}"
  UPSTREAM_PORT="${4:-3010}"
fi

if [[ -z "${EMAIL}" || "${EMAIL}" != *@* ]]; then
  echo "Usage: sudo bash configure_ssl.sh you@example.com" >&2
  echo "   or: sudo bash configure_ssl.sh ${DEFAULT_DOMAIN} you@example.com ${DEFAULT_IP}" >&2
  exit 1
fi

if [[ ! -x "${CERTBOT}" ]]; then
  if command -v certbot >/dev/null 2>&1; then
    CERTBOT="$(command -v certbot)"
  else
    echo "Certbot is missing. Run: sudo bash install_ssl.sh" >&2
    exit 1
  fi
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "Nginx is missing. Run: sudo bash install_ssl.sh" >&2
  exit 1
fi

if [[ ! "${UPSTREAM_PORT}" =~ ^[0-9]+$ ]]; then
  echo "Upstream port must be a number. Got: ${UPSTREAM_PORT}" >&2
  exit 1
fi

if ! "${CERTBOT}" --help all 2>/dev/null | grep -q -- '--ip-address'; then
  echo "This Certbot cannot issue an IP certificate. Run: sudo bash install_ssl.sh" >&2
  exit 1
fi

# Public DNS only. getent also reads /etc/hosts, which on Ubuntu maps this
# hostname to 127.0.1.1 and hides a missing public record.
lookup_public_a() {
  local name="$1"
  local json
  json="$(curl -fsS --max-time 15 -H 'accept: application/dns-json' \
    "https://cloudflare-dns.com/dns-query?name=${name}&type=A" 2>/dev/null || true)"
  if [[ -z "${json}" ]]; then
    echo "lookup-failed"
    return 0
  fi
  python3 -c 'import json,sys
d=json.loads(sys.argv[1])
answers=[a.get("data","") for a in d.get("Answer",[]) if a.get("type")==1]
print(" ".join(answers))' "${json}"
}

PUBLIC_A="$(lookup_public_a "${DOMAIN}")"
DOMAIN_READY=0
if [[ "${PUBLIC_A}" == "lookup-failed" ]]; then
  echo "Warning: could not query public DNS for ${DOMAIN}. The hostname certificate will still be attempted."
  DOMAIN_READY=1
elif [[ -z "${PUBLIC_A}" ]]; then
  echo "Warning: ${DOMAIN} has no public DNS record."
  echo "Let's Encrypt cannot issue a certificate for that name until an A record points at ${IP}."
  echo "https://${IP}/ will still be requested."
else
  DOMAIN_READY=1
  if [[ " ${PUBLIC_A} " != *" ${IP} "* ]]; then
    echo "Warning: ${DOMAIN} public address is ${PUBLIC_A}. Expected ${IP}."
    echo "Let's Encrypt must reach http://${DOMAIN}/ and http://${IP}/ on port 80."
  fi
fi

if ! ss -ltn | grep -q ":${UPSTREAM_PORT} "; then
  echo "Warning: nothing is listening on port ${UPSTREAM_PORT}."
  echo "Start the app first: bash start.sh"
fi

mkdir -p "${WEBROOT}" /etc/letsencrypt/renewal-hooks/deploy /etc/nginx/snippets

cat > /etc/nginx/snippets/chatbot-proxy.conf <<EOF
client_max_body_size 50m;

location / {
    proxy_pass http://127.0.0.1:${UPSTREAM_PORT};
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
EOF

cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/sh
nginx -t && systemctl reload nginx
EOF
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

write_site() {
  cat > "${SITE_PATH}"
  ln -sfn "${SITE_PATH}" "/etc/nginx/sites-enabled/${SITE_NAME}"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx
}

# Port 80 answers the certificate challenge and still proxies the app.
write_site <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} ${IP};

    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
    }

    location / {
        proxy_pass http://127.0.0.1:${UPSTREAM_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF

cert_args=(
  certonly
  --webroot -w "${WEBROOT}"
  --non-interactive
  --agree-tos
  --email "${EMAIL}"
  --keep-until-expiring
)

request_domain() {
  "${CERTBOT}" "${cert_args[@]}" -d "${DOMAIN}" --cert-name "${DOMAIN}"
}

request_ip() {
  "${CERTBOT}" "${cert_args[@]}" \
    --ip-address "${IP}" \
    --preferred-profile shortlived \
    --cert-name "${IP}"
}

request_both() {
  "${CERTBOT}" "${cert_args[@]}" \
    -d "${DOMAIN}" \
    --ip-address "${IP}" \
    --preferred-profile shortlived \
    --cert-name chatbot
}

MODE=""
if [[ "${DOMAIN_READY}" -eq 1 ]]; then
  echo "Requesting one certificate for ${DOMAIN} and ${IP}."
  if request_both; then
    MODE="combined"
  else
    echo "A single certificate for the name and the IP was not issued. Requesting them separately."
    domain_ok=0
    ip_ok=0
    if request_domain; then
      domain_ok=1
    else
      echo "Warning: certificate for ${DOMAIN} was not issued."
    fi
    if request_ip; then
      ip_ok=1
    else
      echo "Warning: certificate for ${IP} was not issued. Port 80 must be reachable from the internet."
    fi
    if [[ "${domain_ok}" -eq 1 && "${ip_ok}" -eq 1 ]]; then
      MODE="split"
    elif [[ "${domain_ok}" -eq 1 ]]; then
      MODE="domain"
      echo "Warning: the IP certificate was not issued. https://${IP}/ will use the name certificate."
    elif [[ "${ip_ok}" -eq 1 ]]; then
      MODE="ip"
    fi
  fi
else
  echo "Skipping ${DOMAIN}. Requesting a certificate for ${IP}."
  if request_ip; then
    MODE="ip"
  else
    echo "Warning: certificate for ${IP} was not issued. Port 80 must be reachable from the internet."
  fi
fi

if [[ -z "${MODE}" ]]; then
  echo "No certificate was issued. Port 80 is still proxying the app." >&2
  exit 1
fi

tune_shortlived() {
  local conf="$1"
  [[ -f "${conf}" ]] || return 0
  if grep -q 'shortlived' "${conf}"; then
    if grep -q '^renew_before_expiry' "${conf}"; then
      sed -i 's/^renew_before_expiry.*/renew_before_expiry = 1 day/' "${conf}"
    else
      printf '\nrenew_before_expiry = 1 day\n' >> "${conf}"
    fi
  fi
}
tune_shortlived /etc/letsencrypt/renewal/chatbot.conf
tune_shortlived "/etc/letsencrypt/renewal/${IP}.conf"

ssl_server() {
  local names="$1"
  local cert_name="$2"
  local default_flag="${3:-}"
  cat <<EOF
server {
    listen 443 ssl ${default_flag};
    listen [::]:443 ssl ${default_flag};
    server_name ${names};

    ssl_certificate /etc/letsencrypt/live/${cert_name}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${cert_name}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    include /etc/nginx/snippets/chatbot-proxy.conf;
}
EOF
}

backup="${SITE_PATH}.bak"
cp "${SITE_PATH}" "${backup}"

{
  cat <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} ${IP};

    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF
  if [[ "${MODE}" == "combined" ]]; then
    ssl_server "${DOMAIN} ${IP}" "chatbot" "default_server"
  elif [[ "${MODE}" == "split" ]]; then
    ssl_server "${DOMAIN}" "${DOMAIN}" "default_server"
    ssl_server "${IP}" "${IP}" ""
  elif [[ "${MODE}" == "ip" ]]; then
    ssl_server "${IP}" "${IP}" "default_server"
  else
    ssl_server "${DOMAIN} ${IP}" "${DOMAIN}" "default_server"
  fi
} > "${SITE_PATH}"

if ! nginx -t; then
  mv "${backup}" "${SITE_PATH}"
  nginx -t
  systemctl reload nginx
  echo "HTTPS config was rejected. Port 80 is still proxying the app." >&2
  exit 1
fi
rm -f "${backup}"
systemctl reload nginx

echo
echo "Frontend and API:"
if [[ "${MODE}" == "ip" ]]; then
  echo "  https://${IP}/"
  echo "  https://${IP}/api/system/health/"
  echo
  echo "${DOMAIN} has no certificate yet. Add a public A record to ${IP}, then run this script again."
else
  echo "  https://${DOMAIN}/"
  echo "  https://${DOMAIN}/api/system/health/"
  echo "  https://${IP}/"
  echo "  https://${IP}/api/system/health/"
fi
echo
echo "backend/.env already trusts both origins. Apply it with:"
echo "  docker compose up -d"
echo
if [[ "${MODE}" == "combined" || "${MODE}" == "split" || "${MODE}" == "ip" ]]; then
  echo "The IP certificate lasts about 6 days. Certbot renews it automatically."
fi
