# ============================================
# Stage 1: Build the Next.js frontend
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Build with empty API URL so the frontend uses relative paths
# (proxied to backend via Next.js rewrites in the unified container)
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Install dependencies first (better layer caching)
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Final image with all services
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including PostgreSQL, Redis, and Node.js
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    nodejs \
    supervisor \
    postgresql \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ ./backend/

# Copy the Next.js standalone build from stage 1
COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public

# Copy supervisor config and entrypoint
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user for app processes and set up directories
RUN useradd -m -u 1000 vibarr \
    && mkdir -p /config /downloads /music /var/log/supervisor /var/run/postgresql \
    && chown -R vibarr:vibarr /app \
    && chown postgres:postgres /var/run/postgresql

LABEL net.unraid.docker.icon="https://github.com/jjermany/Vibarr/raw/main/Logo%20and%20Icon/vibarr-icon.svg"

VOLUME /config
VOLUME /downloads
VOLUME /music

EXPOSE 3000

# Internal service URLs (all localhost within the container)
ENV DATABASE_URL=postgresql://vibarr:vibarr@localhost:5432/vibarr
ENV REDIS_URL=redis://localhost:6379/0
ENV CELERY_BROKER_URL=redis://localhost:6379/1
ENV CELERY_RESULT_BACKEND=redis://localhost:6379/1
ENV SECRET_KEY=change-me-in-production
ENV NODE_ENV=production

ENTRYPOINT ["/entrypoint.sh"]
