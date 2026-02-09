# ============================================
# Stage 1: Build the Next.js frontend
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (better layer caching)
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Final image with backend + frontend
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (Node.js runtime for Next.js standalone + supervisor)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    nodejs \
    supervisor \
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

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create non-root user
RUN useradd -m -u 1000 vibarr \
    && chown -R vibarr:vibarr /app \
    && mkdir -p /var/log/supervisor \
    && chown -R vibarr:vibarr /var/log/supervisor

LABEL net.unraid.docker.icon="/vibarr-icon.svg"

EXPOSE 3000 8000

ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=http://localhost:8000

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
