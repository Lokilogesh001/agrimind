# AgriMind — Deployment Guide

AgriMind can be deployed in multiple environments: local production servers, Docker containers, or cloud virtual machines (AWS, GCP, DigitalOcean) with PostgreSQL.

---

## 1. Local Production Deployment

For bare-metal or on-premise execution:

### 1.1. Build the Frontend
```bash
npm run build
```
This triggers Next.js Turbopack to create an optimized production build in `web/.next`.

### 1.2. Run Production Services
```bash
npm start
```
This launches:
- **FastAPI Backend:** `uvicorn api.main:app --host 127.0.0.1 --port 8000` (production worker mode without hot reload).
- **Next.js Frontend:** `next start` on port 3000.

---

## 2. Docker & Container Deployment

AgriMind includes pre-configured container definitions for both the backend and frontend.

### 2.1. Backend `Dockerfile`
The backend image runs Python 3.12-slim:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2. Multi-Container Orchestration (`docker-compose.yml`)
```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: sqlite:///agrimind_local.db
      DISEASE_MODEL_PATH: ml/artifacts/best.pt
      CORS_ORIGINS: http://localhost:3000
    volumes:
      - ./ml/artifacts:/app/ml/artifacts
      - ./agrimind_local.db:/app/agrimind_local.db

  web:
    image: node:22-alpine
    working_dir: /app/web
    command: sh -c "npm install && npm run dev"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    volumes:
      - ./web:/app/web
    depends_on:
      - api
```

### 2.3. Launch Containers
```bash
docker compose up --build -d
```
Verify status:
```bash
docker compose ps
docker compose logs -f
```

---

## 3. Production Cloud Architecture

For resilient cloud deployment, deploy behind an Nginx reverse proxy:

```mermaid
flowchart TD
    Client(["Internet Clients"]) --> Nginx["Nginx Reverse Proxy\n(Port 80 / 443 SSL)"]
    Nginx -->|/api/*| Uvicorn["Gunicorn / Uvicorn Workers\n(FastAPI - Port 8000)"]
    Nginx -->|/*| NextJS["Node.js Next.js Server\n(Port 3000)"]
    Uvicorn --> DB[("PostgreSQL\n(Supabase / RDS)")]
```

### Sample Nginx Configuration
```nginx
server {
    listen 80;
    server_name agrimind.yourdomain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 4. Production Database Migration (SQLite to PostgreSQL)

To switch from local SQLite to PostgreSQL:
1. Update `DATABASE_URL` in `.env`:
   ```ini
   DATABASE_URL=postgresql+psycopg2://user:password@db.supabase.co:5432/postgres
   ```
2. Run the SQL schema script in your PostgreSQL editor:
   ```bash
   psql $DATABASE_URL -f observability/schema.sql
   ```
3. Restart the backend service. SQLAlchemy will connect and log audit records directly to PostgreSQL.
