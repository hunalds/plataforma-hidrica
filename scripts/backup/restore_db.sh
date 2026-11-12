#!/bin/sh
# Restaura un respaldo hecho con backup_db.sh. ¡REEMPLAZA los datos actuales!
# Uso: sh scripts/backup/restore_db.sh backups/plataforma_hidrica_20261112-020000.dump
# Con Docker: docker compose exec -T backup sh -c 'pg_restore --clean --if-exists --no-owner -d "$PGDATABASE" /backups/ARCHIVO.dump'
set -eu
FILE="${1:?Indica el archivo .dump a restaurar}"
[ -f "$FILE" ] || { echo "No existe $FILE" >&2; exit 1; }
echo "Se restaurará $FILE sobre la base ${PGDATABASE} en ${PGHOST}. Escribe SI para continuar:"
read -r answer
[ "$answer" = "SI" ] || { echo "Cancelado."; exit 1; }
pg_restore --clean --if-exists --no-owner --single-transaction -d "$PGDATABASE" "$FILE"
echo "Restauración terminada. Verifica con: curl http://localhost:8080/api/health"
