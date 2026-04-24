# Toll Navigator — Hetzner Deploy Instructions

## 1. Build the Docker image

```bash
cd ~/Папка\ тест/fixcraftvp/toll-navigator/backend
docker build -t toll-navigator-backend:latest .
```

## 2. Run the container

```bash
docker run -d \
  --name toll-navigator-api \
  --restart unless-stopped \
  -p 127.0.0.1:3001:3001 \
  -e NODE_ENV=production \
  toll-navigator-backend:latest
```

> The DB is baked into the image via `COPY data/toll_navigator.db /app/data/toll_navigator.db`, so no volume mount is required for the toll database.

## 3. Verify it works

```bash
curl http://127.0.0.1:3001/health
```

Expected: `{"status":"ok"}` or similar healthy response.

## 4. Nginx reverse proxy (Hetzner)

Ensure your Nginx site config proxies to the backend:

```nginx
server {
    listen 443 ssl http2;
    server_name api.tollnavigator.com;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Reload Nginx after any config change:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Update / redeploy

```bash
cd ~/Папка\ тест/fixcraftvp/toll-navigator/backend
docker build -t toll-navigator-backend:latest .
docker stop toll-navigator-api
docker rm toll-navigator-api
docker run -d \
  --name toll-navigator-api \
  --restart unless-stopped \
  -p 127.0.0.1:3001:3001 \
  -e NODE_ENV=production \
  toll-navigator-backend:latest
```

## 6. Fix zero-cost toll rates (one-time or as needed)

```bash
cd ~/Папка\ тест/fixcraftvp/toll-navigator/backend
node scripts/fix_zero_rates.js
```

This updates `cost_per_axle` for all records where both `cost_per_axle=0` and `min_cost=0` using realistic state averages.
