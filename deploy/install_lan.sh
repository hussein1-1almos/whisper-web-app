#!/usr/bin/env bash
set -euo pipefail

# Run as root after editing LAN_CIDR and APP_SOURCE below.
LAN_CIDR="${LAN_CIDR:-192.168.1.0/24}"
APP_SOURCE="${APP_SOURCE:-}"

if [[ -z "$APP_SOURCE" || ! -f "$APP_SOURCE/iraqi_listener.py" ]]; then
  echo "Set APP_SOURCE to the folder containing iraqi_listener.py."
  echo "Example: sudo APP_SOURCE=/home/youruser/voice_summrizer LAN_CIDR=192.168.1.0/24 $0"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo."
  exit 1
fi

apt-get update
apt-get install -y ufw curl rsync debian-keyring debian-archive-keyring apt-transport-https

# Install Caddy from its official Debian/Ubuntu repository if it is not present.
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y curl gnupg
  install -d -m 0755 /etc/apt/keyrings
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /etc/apt/keyrings/caddy-stable-archive-keyring.gpg
  chmod 0644 /etc/apt/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    -o /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy
fi

if ! id voiceapp >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /opt/voice_summrizer --shell /usr/sbin/nologin voiceapp
fi
install -d -o voiceapp -g voiceapp /opt/voice_summrizer

# Copy project while preserving the existing Python environment only if it lives in APP_SOURCE.
# The app's virtual environment must be created at /opt/voice_summrizer/.venv.
rsync -a --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  "$APP_SOURCE/" /opt/voice_summrizer/
chown -R voiceapp:voiceapp /opt/voice_summrizer

install -m 0644 "$(dirname "$0")/Caddyfile" /etc/caddy/Caddyfile
install -m 0644 "$(dirname "$0")/voice-summrizer.service" /etc/systemd/system/voice-summrizer.service

# Keep SSH reachable; expose HTTPS only to the selected private subnet.
ufw allow OpenSSH
ufw allow from "$LAN_CIDR" to any port 443 proto tcp
ufw deny 8000/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable voice-summrizer
systemctl enable caddy

echo
echo "Files installed. Before starting the app:"
echo "  1) Create /opt/voice_summrizer/.venv and install your app requirements."
echo "  2) Ensure live_router.py and web/ are inside /opt/voice_summrizer."
echo "  3) Configure local DNS or client hosts entries: voice.home.arpa -> this server's LAN IP."
echo "  4) Start services: systemctl start voice-summrizer && systemctl restart caddy"
echo "  5) Trust Caddy's internal root CA on each client (see README_UBUNTU_LAN.md)."
