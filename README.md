# howisvlad.today

My public life dashboard — a living snapshot of what I'm up to, where I've been, and what's keeping me busy.

**Live at [howisvlad.today](https://howisvlad.today)**

---

## What is this?

A personal dashboard website built entirely from scratch — no templates, no frameworks, no CMS. Raw HTML, D3.js, Python, and a VPS. Everything from infrastructure provisioning to data pipelines to frontend visualizations was built by hand.

## Pages

| Page | Path | Description | Status |
|------|------|-------------|--------|
| Landing | `/` | Overview and navigation hub | ✅ Live |
| Health & Fitness | `/health/` | Strava activity dashboard with interactive charts | ✅ Live |
| Travel | `/travel/` | Where I've been and where I'm heading | 🔜 Coming soon |
| Reading | `/reading/` | Books I'm reading and have read | 🔜 Coming soon |
| Photos | `/photos/` | Latest snapshots | 🔜 Coming soon |
| Projects | `/projects/` | What I'm building | 🔜 Coming soon |

## Health Dashboard

The health page pulls data from the Strava API and visualizes it with D3.js:

- **Weekly mileage** — bar chart with activity type filters
- **Pace trend** — scatter plot with rolling average, filterable by distance
- **Activity calendar** — GitHub-style heatmap showing daily activity
- **Summary stats** — total distance, activity count, heart rate averages
- **Year selector** — filter all charts by year or view all time

Data is synced automatically twice a week via Apache Airflow.

## Architecture

```
┌─────────────┐      ┌──────────────────────────────────────────┐
│  Strava API  │◄────►│  Hetzner VPS (CAX11)                     │
└─────────────┘      │                                          │
                     │  Airflow (Docker) ─► PostgreSQL           │
┌─────────────┐      │                                          │
│  Namecheap   │─DNS─►│  Nginx (SSL) ─► FastAPI ─► D3.js        │
│  (DNS only)  │      │                                          │
└─────────────┘      └──────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Server | Hetzner CAX11 (ARM64, 2 vCPU, 4GB RAM) |
| OS | Ubuntu 24.04 LTS |
| Web server | Nginx + Let's Encrypt SSL |
| Database | PostgreSQL 16 |
| Pipeline | Apache Airflow 2.x (Docker Compose) |
| API | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS + D3.js |
| Deploy | GitHub Actions (auto-deploy on push) |

## Project Structure

```
site/                       # Static files → served by Nginx
├── index.html              # Landing page
└── health/
    └── index.html          # Health dashboard (D3.js)

health/                     # Strava data pipeline & API
├── api/
│   └── main.py             # FastAPI endpoints
├── strava/
│   └── client.py           # Strava API client with token refresh
├── airflow/
│   └── dags/
│       └── strava_sync_dag.py
├── sync.py                 # Data sync: Strava → PostgreSQL
└── docker-compose.yml      # Airflow services

.github/workflows/
└── deploy.yml              # Auto-deploy on push to main
```

## How It Works

1. **Airflow** runs a DAG every Monday and Friday at 8am UTC
2. The DAG refreshes the Strava OAuth token and fetches new activities
3. Activities are upserted into **PostgreSQL** with full JSON stored for future use
4. **FastAPI** serves pre-aggregated data (weekly stats, pace data, calendar data) as JSON
5. **D3.js** fetches from the API and renders interactive charts client-side
6. **Nginx** handles SSL termination, serves static files, and proxies API/Airflow requests

## Deployment

Pushing to `main` triggers a GitHub Actions workflow that:
1. SSHes into the server
2. Pulls latest code
3. Syncs static files to the web root via `rsync`
4. Restarts the FastAPI service
5. Refreshes Airflow containers

## Running Your Own

1. Provision a VPS and install Docker, PostgreSQL, Nginx
2. Clone this repo
3. Copy `.env.example` to `.env` and fill in your credentials
4. Register a [Strava API application](https://www.strava.com/settings/api)
5. Complete the OAuth flow to get your refresh token
6. Run `python health/sync.py --full` for initial data load
7. Start Airflow: `cd health && docker compose --env-file ../.env up -d`
8. Start the API: configure and enable the systemd service
9. Configure Nginx to serve `site/` and proxy `/api/` and `/airflow/`

## Cost

| Item | Cost |
|------|------|
| Hetzner CAX11 | €3.29/month |
| Domain (Namecheap) | ~€2/year |
| Everything else | Free |
| **Total** | **~€3.45/month** |

---

Built from scratch in Belgrade, Serbia.