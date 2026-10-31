# Ubuntu LAN deployment — Iraqi Arabic Voice Intelligence

This bundle adds LAN deployment files to the existing FastAPI project. It uses:
- FastAPI/Uvicorn on `127.0.0.1:8000` (not directly exposed to the LAN)
- Caddy as an HTTPS reverse proxy on TCP 443
- Caddy's internal certificate authority
- UFW rules allowing HTTPS only from the configured private subnet
- systemd to keep the API running

## Before deployment\n\nFor the exact integration with your public repository, follow `INTEGRATE_WITH_YOUR_SERVER.md` first. The live router has been corrected to use a NumPy waveform and your existing `whisper_lock`.\n

You need the existing project folder containing `iraqi_listener.py`, its Python requirements, and the existing Whisper/Qwen model setup. This bundle does not replace your models or rewrite the existing `/transcribe` endpoint.

The web files in `web/` and `live_router.py` are the browser interface/live-audio add-on. The FastAPI integration is described in `README_INSTALL.md`. Confirm the integration uses the actual names in your server source before starting.

## 1. Copy the project to Ubuntu

Example:

```bash
sudo mkdir -p /opt/voice_summrizer
sudo rsync -a /path/to/your/voice_summrizer/ /opt/voice_summrizer/
```

Copy this bundle's `live_router.py` and `web/` into `/opt/voice_summrizer/` if they are not already there.

Create a service account and virtual environment:

```bash
sudo useradd --system --create-home --home-dir /opt/voice_summrizer --shell /usr/sbin/nologin voiceapp
sudo chown -R voiceapp:voiceapp /opt/voice_summrizer
sudo -u voiceapp python3 -m venv /opt/voice_summrizer/.venv
sudo -u voiceapp /opt/voice_summrizer/.venv/bin/pip install --upgrade pip
sudo -u voiceapp /opt/voice_summrizer/.venv/bin/pip install -r /opt/voice_summrizer/requirements.txt
sudo -u voiceapp /opt/voice_summrizer/.venv/bin/pip install numpy
```

If your current server uses a different environment or requirements filename, install the exact same compatible dependencies into this venv. Do not blindly reinstall CUDA/PyTorch packages if your existing setup is already working.

## 2. Integrate the web interface

Follow `README_INSTALL.md` to add the live router, static web directory, and `/` route to `iraqi_listener.py`. The service expects the import path `iraqi_listener:app`.

Important: the earlier prototype assumes `whisper_model` and `summarize_transcript` exist and that the Whisper call accepts the audio object passed by `live_router.py`. Verify these against your actual code. If your app has different names or uses a different audio input method, the router must be adapted before production use.

## 3. Choose the LAN subnet

Find the server IP and subnet:

```bash
ip -br address
ip route
```

Example only: if your server is `192.168.1.50` and the LAN is `192.168.1.0/24`, use that CIDR. Do not assume this example matches your network.

## 4. Install the LAN configuration

From the extracted bundle:

```bash
sudo APP_SOURCE=/path/to/your/voice_summrizer LAN_CIDR=192.168.1.0/24 bash deploy/install_lan.sh
```

Replace both values. The script copies the app to `/opt/voice_summrizer`, installs Caddy if needed, installs the systemd unit and Caddyfile, and enables UFW rules. Review the script before running it. If UFW is already managed by your organization, add equivalent rules through your normal firewall instead.

Then create the virtual environment and install requirements as described above. Start:

```bash
sudo systemctl start voice-summrizer
sudo systemctl restart caddy
sudo systemctl status voice-summrizer --no-pager
sudo systemctl status caddy --no-pager
```

Logs:

```bash
sudo journalctl -u voice-summrizer -f
sudo journalctl -u caddy -f
```

## 5. Give the server a private hostname

The chosen URL is:

`https://voice.home.arpa`

Configure your router's local DNS to resolve `voice.home.arpa` to the Ubuntu server's LAN IP. If your router cannot provide local DNS, add a hosts-file entry on each client computer.

Windows hosts file (run Notepad as Administrator; edit `C:\Windows\System32\drivers\etc\hosts`):

```text
192.168.1.50    voice.home.arpa
```

Replace the IP with the actual server IP. For managed environments, prefer internal DNS.

## 6. Trust the internal HTTPS certificate

Caddy generates a local root CA. On the Ubuntu server, locate its root certificate:

```bash
sudo find /var/lib/caddy -name root.crt -print
```

Usually it is:

`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt`

Copy this certificate securely to each authorized client and install it as a trusted **root CA** in that client's operating system trust store. Do not distribute `root.key` or any private key. Restart the browser after trusting the certificate.

For Windows, open `mmc.exe` → Add/Remove Snap-in → Certificates → Computer account → Trusted Root Certification Authorities → Certificates → Import, then select `root.crt`. Only do this for a CA you control and whose fingerprint you have verified through a trusted channel.

If Caddy runs under a different data directory, use the path reported by `find`. Do not copy the CA private key.

## 7. Test

From a LAN client:
- Open `https://voice.home.arpa`
- Confirm the browser shows a valid trusted HTTPS connection.
- Test audio upload.
- Test microphone permission.
- Test tab sharing and select the meeting tab with **Share tab audio** enabled.

The browser may deny microphone/tab capture if the certificate is not trusted, even though the page itself loads.

## Network security

- Uvicorn binds only to `127.0.0.1`; clients cannot bypass Caddy via port 8000.
- Caddy rejects requests outside RFC1918 private IPv4 ranges.
- UFW allows TCP 443 only from the configured LAN CIDR and denies TCP 8000.
- Do not add router port-forwarding for 443 or 8000.
- The Caddy IP filter is an additional layer, not user authentication. Anyone on the allowed LAN can access the app unless you add authentication.
- For sensitive deployments, add login/authentication, per-user session isolation, retention/deletion controls, request limits, audit logs, and a consent process before use.
- If your LAN uses IPv6, add an explicit IPv6 policy; the sample Caddy matcher is IPv4-private-only. Disable public IPv6 exposure or adapt the firewall and matcher.
- Browser tab capture works only for browser tabs whose audio the user explicitly shares. It does not capture the desktop Discord app.

## Troubleshooting

```bash
sudo ss -lntp | grep -E ':443|:8000'
sudo ufw status verbose
sudo journalctl -u voice-summrizer -n 100 --no-pager
sudo journalctl -u caddy -n 100 --no-pager
```

Expected listeners:
- Caddy on `:443`
- Uvicorn on `127.0.0.1:8000`

If Uvicorn fails, check the import path, virtualenv, environment variables, model paths/permissions, and startup logs. Loading large models can take time; systemd may show the service as starting while the models load.
