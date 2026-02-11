#!/bin/bash
set -e

PG_BIN=/usr/lib/postgresql/15/bin
PG_DATA=/config/postgresql

# Ensure /config is traversable for service users (postgres/redis)
mkdir -p /config
chmod 755 /config

# ── Auto-generate secret key if not provided ──
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "change-me-in-production" ]; then
    if [ -f /config/.secret_key ]; then
        export SECRET_KEY=$(cat /config/.secret_key)
    else
        export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        mkdir -p /config
        echo "$SECRET_KEY" > /config/.secret_key
        chmod 600 /config/.secret_key
        echo "Generated new secret key."
    fi
fi

# ── Initialize PostgreSQL on first run ──
if [ ! -f "$PG_DATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database..."
    mkdir -p "$PG_DATA"
    chown postgres:postgres "$PG_DATA"
    su -c "$PG_BIN/initdb -D $PG_DATA" postgres

    # Local-only access
    cat >> "$PG_DATA/postgresql.conf" << 'EOF'
listen_addresses = '127.0.0.1'
unix_socket_directories = '/var/run/postgresql'
EOF

    # Trust local connections (internal to container only)
    cat > "$PG_DATA/pg_hba.conf" << 'EOF'
local   all   all                 trust
host    all   all   127.0.0.1/32  trust
EOF

    # Start temporarily to create the vibarr database
    su -c "$PG_BIN/pg_ctl -D $PG_DATA start -w -o '-k /var/run/postgresql'" postgres
    su -c "$PG_BIN/psql -h 127.0.0.1 -c \"CREATE USER vibarr WITH PASSWORD 'vibarr';\"" postgres
    su -c "$PG_BIN/psql -h 127.0.0.1 -c \"CREATE DATABASE vibarr OWNER vibarr;\"" postgres
    su -c "$PG_BIN/pg_ctl -D $PG_DATA stop -w" postgres
    echo "PostgreSQL initialized successfully."
fi

# ── Ensure directories and permissions ──
mkdir -p /config/redis /var/run/postgresql
chown -R postgres:postgres "$PG_DATA"
chmod 700 "$PG_DATA"
[ -f "$PG_DATA/postgresql.conf" ] && chmod 600 "$PG_DATA/postgresql.conf"
[ -f "$PG_DATA/pg_hba.conf" ] && chmod 600 "$PG_DATA/pg_hba.conf"
chown postgres:postgres /var/run/postgresql
chown redis:redis /config/redis

exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
