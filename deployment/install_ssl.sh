#!/usr/bin/env bash
# Install Nginx and a current Certbot on Ubuntu 24.04 (noble).
# Certbot 5.4 or newer is required for a certificate that includes the IP address.
# Run on the server, from this folder: sudo bash install_ssl.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash install_ssl.sh" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Cannot read /etc/os-release. This script is for Ubuntu 24.04." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" ]]; then
  echo "This script is for Ubuntu 24.04 (noble). Found: ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl nginx snapd

systemctl enable --now nginx
systemctl enable --now snapd.socket
systemctl start snapd.socket

# The apt Certbot on Ubuntu 24.04 cannot issue IP-address certificates.
apt-get remove -y certbot python3-certbot-nginx >/dev/null 2>&1 || true

snap install core
snap refresh core || true
snap install --classic certbot
snap refresh --classic certbot || true
ln -sfn /snap/bin/certbot /usr/local/bin/certbot

if systemctl list-unit-files | grep -q '^snap.certbot.renew.timer'; then
  systemctl enable --now snap.certbot.renew.timer
fi

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
fi

echo
echo "Installed Nginx and Certbot on ${PRETTY_NAME}."
certbot --version || true
echo "Start the containers first (bash start.sh), then run:"
echo "  sudo bash configure_ssl.sh you@example.com"
