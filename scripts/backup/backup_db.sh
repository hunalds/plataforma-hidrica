#!/bin/sh
# Respaldo de PostgreSQL en formato personalizado (pg_dump -Fc) con retención por días.
# Variables: PGHOST, PGDATABASE, PGUSER, PGPASSWORD, BACKUP_DIR (por defecto /backups), BACKUP_KEEP_DAYS (14).
# Uso manual:   sh scripts/backup/backup_db.sh
# Con cron:     0 2 * * * cd /opt/plataforma-hidrica && docker compose exec -T backup sh /usr/local/bin/backup_db.sh
set -eu
BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="${BACKUP_DIR}/${PGDATABASE}_${STAMP}.dump"

mkdir -p "$BACKUP_DIR"
pg_dump --format=custom --compress=9 --no-owner --file="${FILE}.tmp"
mv "${FILE}.tmp" "$FILE"
# Verificación: el archivo debe poder listarse
pg_restore --list "$FILE" > /dev/null
echo "$(date -Iseconds) respaldo OK: $FILE ($(du -h "$FILE" | cut -f1))"

# Retención
find "$BACKUP_DIR" -name "${PGDATABASE}_*.dump" -type f -mtime "+${KEEP}" -print -delete
