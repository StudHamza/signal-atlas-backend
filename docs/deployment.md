# Deployment

## Required GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

| Secret | Example | Description |
|--------|---------|-------------|
| `VPS_HOST` | `123.45.67.89` | VPS IP or hostname |
| `VPS_USER` | `ubuntu` | SSH username |
| `VPS_SSH_KEY` | *(private key contents)* | SSH private key (no passphrase) |
| `VPS_PORT` | `22` | SSH port (optional, defaults to 22) |
| `APP_DIR` | `/opt/network-monitor` | Absolute path to the repo on the VPS |

## How it works

1. A push to `main` triggers the **CI** workflow first — tests must pass.
2. If tests pass, the **Deploy** workflow SSHs into the VPS and runs:
   ```bash
   git pull origin main
   docker compose up -d --build --remove-orphans
   docker image prune -f
   ```
3. The `concurrency: production` lock prevents two deploys racing each other.

## VPS first-time setup

```bash
# On your VPS
git clone https://github.com/<you>/<repo>.git /opt/network-monitor
cd /opt/network-monitor
cp .env.example .env   # fill in real values
docker compose up -d --build
```

After that, every push to `main` deploys automatically.