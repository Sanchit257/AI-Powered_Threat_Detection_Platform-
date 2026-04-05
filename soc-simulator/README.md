# SOC Simulator

AI-Powered Threat Detection Platform scaffold: log simulator, ML engine stub, FastAPI backend, React dashboard, Redis, Postgres, and Nginx.

## Prerequisites

- Docker and Docker Compose v2

## Setup

```bash
cd soc-simulator
cp .env.example .env
```

Edit `.env` if needed (API keys are optional for the placeholder stack).

## Run

```bash
make up
```

- **Nginx (integrated):** http://localhost/ (dashboard), http://localhost/api/ (API)
- **Direct:** API http://localhost:8000, dashboard http://localhost:3000

For Vite HMR during frontend development, use http://localhost:3000 directly; Nginx is mainly for a single-entry preview.

## Seed test data

With the stack up (Redis reachable):

```bash
make seed
```

Runs the log simulator once (`--once`) to push sample events to Redis.

## Makefile targets

| Target   | Command                          |
| -------- | -------------------------------- |
| `make up`   | `docker compose up --build`    |
| `make down` | `docker compose down`          |
| `make logs` | `docker compose logs -f`       |
| `make seed` | One-shot simulator run         |

## Health checks

```bash
curl -s http://localhost/api/health
curl -s http://localhost:8000/health
```
