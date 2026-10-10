# Deploying to one AWS EC2 server

This runs the whole stack with Docker Compose on a single EC2 instance, behind
Nginx with a free Let's Encrypt certificate. It is a demo deployment: one
server, no autoscaling, and only synthetic data.

## 1. Create the server

1. EC2 console → Launch instance.
   - Image: Ubuntu Server 24.04 LTS.
   - Type: `t3.large` (8 GB RAM). The embedding model, spaCy model and XGBoost
     need about 3 GB; smaller instances run out of memory while building.
   - Storage: 30 GB gp3.
   - Key pair: create one and keep the `.pem` file.
2. Security group: allow inbound
   - 22 (SSH) from **your IP only**,
   - 80 and 443 from anywhere.
   Do not open 5432, 6379, 8000 or 3000.
3. Allocate an Elastic IP and attach it to the instance, so the address does not
   change after a restart.
4. At your domain registrar, add an `A` record (for example `claimguard.yourdomain.com`)
   pointing at the Elastic IP.

## 2. Install Docker and Nginx

```bash
ssh -i your-key.pem ubuntu@<elastic-ip>

sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
sudo apt install -y nginx certbot python3-certbot-nginx git
exit   # log in again so the docker group applies
```

## 3. Get the code and configure secrets

```bash
git clone https://github.com/<you>/claimguard.git
cd claimguard
cp .env.example .env
nano .env
```

In `.env` set a strong `POSTGRES_PASSWORD`, put the same password in
`DATABASE_URL`, and set `ANTHROPIC_API_KEY`. `.env` is in `.gitignore`; never
commit it.

## 4. Start the stack and run setup

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose run --rm api bash /project/scripts/setup.sh
docker compose restart api        # loads the newly trained risk model
docker compose ps                 # every service should be "running"/"healthy"
curl -s http://127.0.0.1:3000/api/health
```

`docker-compose.prod.yml` removes the public ports of PostgreSQL, Redis and the
API, and binds the frontend to `127.0.0.1:3000`, so only Nginx can reach it.

## 5. Nginx and HTTPS

```bash
sudo cp deploy/nginx-claimguard.conf /etc/nginx/sites-available/claimguard
sudo nano /etc/nginx/sites-available/claimguard     # set server_name to your domain
sudo ln -s /etc/nginx/sites-available/claimguard /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d claimguard.yourdomain.com
```

Certbot installs the certificate, adds the HTTPS block and redirects HTTP to
HTTPS. It also sets up automatic renewal (`sudo certbot renew --dry-run` to check).

## 6. Updating

```bash
cd claimguard
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Database migrations run automatically when the API container starts.

## Operating notes

- Logs: `docker compose logs -f api`. Logs contain request ids, case ids and
  timings, never document text.
- Backups: `docker compose exec database pg_dump -U claimguard claimguard > backup.sql`.
- Cost: a `t3.large` is roughly $60 per month if left running; stop the
  instance when you are not demoing.
- This setup is not suitable for real patient data. That would need a HIPAA
  Business Associate Agreement with AWS and the LLM provider, encryption at
  rest, private subnets, access controls and audit retention policies.
