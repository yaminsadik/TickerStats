# Docker Quick Reference

## Files Created

- ✅ `Dockerfile` - Production container image
- ✅ `.dockerignore` - Excludes unnecessary files from image
- ✅ `docker-compose.yml` - Local testing (optional)
- ✅ `DIGITALOCEAN_DEPLOY.md` - Full deployment guide

## FastAPI App Configuration

**Import Path**: `app.main:app`

- Module: `app.main` (located at `/app/app/main.py` in container)
- Application: `app` (FastAPI instance)

**Health Endpoint**: `/health`

- Returns: `{"status": "ok"}`
- Used for Docker healthcheck and DigitalOcean health monitoring

## Quick Commands

### Local Testing with Docker

```bash
# Build image
docker build -t ticketstats-api .

# Run with environment variables
docker run -p 5000:5000 \
  -e DATABASE_URL="postgresql://user:pass@localhost/db" \
  -e ASYNC_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db" \
  -e AUTH0_DOMAIN="domain.auth0.com" \
  -e AUTH0_API_AUDIENCE="https://api-audience" \
  ticketstats-api

# Using docker-compose (includes PostgreSQL)
docker-compose up -d
docker-compose logs -f api

# Run migrations
docker-compose exec api alembic upgrade head

# Stop services
docker-compose down
```

### DigitalOcean Deployment

```bash
# Via UI: Upload to GitHub/GitLab → Create App → Configure (see DIGITALOCEAN_DEPLOY.md)

# Via CLI:
doctl apps create --spec app-spec.yaml
doctl apps list
doctl apps logs YOUR_APP_ID --follow
```

## Environment Variables (Required)

```bash
DATABASE_URL=postgresql://user:pass@host:port/database
ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/database
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_API_AUDIENCE=https://your-api-audience
AUTH0_ALGORITHMS=RS256
```

## Container Specifications

- **Base Image**: python:3.12-slim
- **Port**: 5000
- **Server**: Gunicorn + Uvicorn workers (2 workers default)
- **User**: Non-root (appuser, UID 1000)
- **Healthcheck**: HTTP GET `/health` every 30s

## Testing

```bash
# Health check
curl http://localhost:5000/health

# API documentation
open http://localhost:5000/docs

# Test relative API (requires auth)
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:5000/api/relative?symbols=AAPL,MSFT"
```

## Production Notes

1. **Secrets**: Set via DigitalOcean environment variables (never in Dockerfile)
2. **Migrations**: Run `alembic upgrade head` before first deployment
3. **Scaling**: Start with basic-xxs, scale up based on metrics
4. **CORS**: Update `allow_origins` in `app/main.py` for production domains
5. **Monitoring**: Use DigitalOcean App Platform insights + logs

See `DIGITALOCEAN_DEPLOY.md` for complete deployment instructions.
