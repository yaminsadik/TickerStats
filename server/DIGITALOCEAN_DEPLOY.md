# DigitalOcean Deployment Guide

## Prerequisites

- DigitalOcean account
- PostgreSQL database (DigitalOcean Managed Database or external)
- Auth0 account configured (domain, audience, etc.)

## Deployment Steps

### 1. Build and Test Locally (Optional)

```bash
cd server

# Build the Docker image
docker build -t ticketstats-api .

# Test locally with environment variables
docker run -p 5000:5000 \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  -e ASYNC_DATABASE_URL="postgresql+asyncpg://user:pass@host/db" \
  -e AUTH0_DOMAIN="your-domain.auth0.com" \
  -e AUTH0_API_AUDIENCE="your-audience" \
  -e AUTH0_ALGORITHMS="RS256" \
  ticketstats-api

# Verify health endpoint
curl http://localhost:5000/health
```

### 2. Deploy to DigitalOcean App Platform

#### Option A: Using the DigitalOcean UI

1. **Create a New App**
   - Go to App Platform in DigitalOcean dashboard
   - Click "Create App"
   - Connect your GitHub/GitLab repository
   - Select the repository and branch

2. **Configure the Service**
   - **Type**: Web Service
   - **Source Directory**: `/server`
   - **Dockerfile Path**: `/server/Dockerfile`
   - **HTTP Port**: `5000`
   - **HTTP Request Routes**: `/` (all routes)
   - **Health Check Path**: `/health`
3. **Set Environment Variables**
   Add the following environment variables in the App Platform settings:

   ```bash
   # Database
   DATABASE_URL=postgresql://username:password@host:port/database
   ASYNC_DATABASE_URL=postgresql+asyncpg://username:password@host:port/database

   # Auth0
   AUTH0_DOMAIN=your-domain.auth0.com
   AUTH0_API_AUDIENCE=https://your-api-audience
   AUTH0_ALGORITHMS=RS256

   # Optional: Application Settings
   API_VERSION=1.0.0
   DEBUG=false
   LOG_LEVEL=info

   # CORS (if needed)
   ALLOWED_ORIGINS=https://your-frontend-domain.com
   ```

4. **Configure Resources**
   - **Instance Size**: Basic (512MB RAM) or Professional (1GB+ recommended)
   - **Instance Count**: 1-3 (depending on load)

5. **Run Database Migrations**
   - Add a **Job** component (optional) or use the console
   - Command: `alembic upgrade head`
   - Run this before or after the first deployment

#### Option B: Using doctl CLI

```bash
# Install doctl and authenticate
doctl auth init

# Create app spec file (see app-spec.yaml below)
doctl apps create --spec app-spec.yaml

# Update app
doctl apps update YOUR_APP_ID --spec app-spec.yaml
```

### 3. App Spec Configuration (app-spec.yaml)

Create this file for CLI-based deployment:

```yaml
name: ticketstats-api
region: nyc

services:
  - name: api
    github:
      repo: your-username/ticketstats
      branch: main
      deploy_on_push: true

    dockerfile_path: server/Dockerfile
    source_dir: /server

    http_port: 5000

    health_check:
      http_path: /health
      initial_delay_seconds: 30
      period_seconds: 10
      timeout_seconds: 5
      success_threshold: 1
      failure_threshold: 3

    instance_count: 1
    instance_size_slug: basic-xxs

    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL} # Reference managed DB

      - key: AUTH0_DOMAIN
        scope: RUN_TIME
        value: your-domain.auth0.com

      - key: AUTH0_API_AUDIENCE
        scope: RUN_TIME
        value: https://your-api-audience

      - key: AUTH0_ALGORITHMS
        scope: RUN_TIME
        value: RS256

      - key: DEBUG
        scope: RUN_TIME
        value: "false"

databases:
  - name: db
    engine: PG
    version: "15"
    size: db-s-dev-database
    num_nodes: 1
```

### 4. Running Database Migrations

#### Option A: Using App Platform Console

1. Go to your App → Console tab
2. Run: `alembic upgrade head`

#### Option B: Add a Pre-Deploy Job

Add this to your `app-spec.yaml`:

```yaml
jobs:
  - name: migrate
    github:
      repo: your-username/ticketstats
      branch: main

    dockerfile_path: server/Dockerfile
    source_dir: /server

    kind: PRE_DEPLOY

    run_command: alembic upgrade head

    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
```

#### Option C: SSH into the container

```bash
# Get app ID
doctl apps list

# SSH into running container
doctl apps exec YOUR_APP_ID --component api

# Run migration
alembic upgrade head
```

### 5. Verify Deployment

```bash
# Check health endpoint
curl https://your-app.ondigitalocean.app/health

# Expected response:
{"status":"ok"}

# Test API docs
https://your-app.ondigitalocean.app/docs

# Test a protected endpoint (requires auth token)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  https://your-app.ondigitalocean.app/api/relative?symbols=AAPL,MSFT
```

### 6. Monitoring and Logs

- **View Logs**: App Platform → Runtime Logs
- **Metrics**: App Platform → Insights (CPU, Memory, Request Rate)
- **Alerts**: Set up alerts for health check failures

### 7. Scaling

To handle more traffic:

```bash
# Scale horizontally (more instances)
doctl apps update YOUR_APP_ID --spec app-spec.yaml
# (Update instance_count in spec)

# Scale vertically (larger instances)
# Update instance_size_slug to:
# - basic-xs (1GB RAM)
# - basic-s (2GB RAM)
# - professional-xs, professional-s, etc.
```

## Environment Variables Reference

| Variable           | Required | Default | Description                                   |
| ------------------ | -------- | ------- | --------------------------------------------- |
| `DATABASE_URL`     | Yes      | -       | PostgreSQL sync connection string (psycopg2)  |
| `ASYNC_DATABASE_URL` | Yes    | -       | PostgreSQL async connection string (asyncpg)   |
| `AUTH0_DOMAIN`     | Yes      | -       | Auth0 tenant domain                           |
| `AUTH0_API_AUDIENCE` | Yes      | -       | Auth0 API audience/identifier               |
| `AUTH0_ALGORITHMS` | No       | `RS256` | JWT verification algorithm                    |
| `API_VERSION`      | No       | `1.0.0` | API version string                            |
| `DEBUG`            | No       | `false` | Enable debug mode                             |
| `LOG_LEVEL`        | No       | `info`  | Logging level (debug, info, warning, error)   |
| `ALLOWED_ORIGINS`  | No       | `*`     | CORS allowed origins (comma-separated)        |

## Troubleshooting

### Health check failing

- Check logs for startup errors
- Verify DATABASE_URL is correct
- Ensure port 5000 is properly exposed
- Increase `initial_delay_seconds` if app needs more time to start

### Database connection errors

- Verify DATABASE_URL format: `postgresql://user:pass@host:port/database`
- Verify ASYNC_DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/database`
- Check firewall rules (DigitalOcean Managed DB has trusted sources)
- Ensure database migrations have run

### Auth0 errors

- Verify AUTH0_DOMAIN doesn't include `https://`
- Check AUTH0_API_AUDIENCE matches your API identifier
- Ensure Auth0 Application has correct callback URLs

### Migration issues

```bash
# Check current migration status
alembic current

# View migration history
alembic history

# Rollback one version
alembic downgrade -1

# Upgrade to latest
alembic upgrade head
```

## Cost Optimization

- Start with **basic-xxs** ($5/month) for testing
- Use **basic-xs** ($12/month) for production with moderate traffic
- Enable **autoscaling** (1-3 instances) for traffic spikes
- Use DigitalOcean Managed Database **dev tier** ($15/month) for testing

## Security Best Practices

1. **Never commit secrets** - Use App Platform environment variables
2. **Use managed database** - Automatic backups and security patches
3. **Enable HTTPS** - Automatic with App Platform
4. **Restrict CORS** - Set specific `ALLOWED_ORIGINS` in production
5. **Review Auth0 settings** - Ensure proper token validation
6. **Regular updates** - Keep dependencies up to date

## Next Steps

- Set up custom domain in App Platform settings
- Configure automated backups for PostgreSQL
- Set up monitoring alerts (health checks, error rates)
- Implement CI/CD for automated deployments
- Review and optimize instance sizing based on metrics
