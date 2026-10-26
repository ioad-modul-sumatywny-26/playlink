#!/bin/sh
set -e

echo "=== Starting Playlink All-in-One Appliance ==="

export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
export POSTGRES_USER="${POSTGRES_USER:-playlink}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-playlink}"
export POSTGRES_DB="${POSTGRES_DB:-playlink}"

# Ensure directories exist and have proper permissions
mkdir -p "$PGDATA" /var/run/postgresql /var/log/supervisor /var/run
chown -R postgres:postgres "$PGDATA" /var/run/postgresql
chmod 0700 "$PGDATA"

# Map frontend and backend to localhost in /etc/hosts for compatibility with compose-style tunnel configs
if ! grep -q "frontend" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 frontend backend" >> /etc/hosts 2>/dev/null || true
fi

# Remove any stale lock files from previous unclean shutdowns
rm -f /var/run/supervisord.pid "$PGDATA/postmaster.pid" /var/run/postgresql/.s.PGSQL.5432*

# Initialize database cluster if not already present
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[entrypoint] Initializing fresh PostgreSQL cluster in $PGDATA..."
    gosu postgres initdb -D "$PGDATA" -E UTF8 --locale=C.UTF-8

    echo "[entrypoint] Temporarily starting PostgreSQL for initialization..."
    gosu postgres pg_ctl -D "$PGDATA" -o "-c listen_addresses='127.0.0.1'" -w start

    echo "[entrypoint] Setting up database '$POSTGRES_DB' and user '$POSTGRES_USER'..."
    gosu postgres psql -v ON_ERROR_STOP=1 <<-EOSQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
                CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD}';
            ELSE
                ALTER ROLE ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
            END IF;
        END
        \$\$;

        SELECT 'CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER}'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}')\gexec

        GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
EOSQL

    echo "[entrypoint] Shutting down temporary PostgreSQL instance..."
    gosu postgres pg_ctl -D "$PGDATA" -m fast -w stop
    echo "[entrypoint] PostgreSQL initial setup complete."
fi

# Ensure permissions on PGDATA remain strictly owned by postgres
chown -R postgres:postgres "$PGDATA"

echo "[entrypoint] Launching supervisor daemon..."
exec supervisord -c /etc/supervisor/supervisord.conf -n
