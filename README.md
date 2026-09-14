# ClaimGuard

An AI copilot that checks lumbar spine MRI prior-authorization requests against
insurer coverage policy before they are submitted.

> **Decision support only. A human reviewer makes the final decision.**
> All patient data in this project is synthetic.

## Status

Work in progress.

## Quick start

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

## Running tests locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
