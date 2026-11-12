"""Activa la extensión PostGIS.

La extensión la crea scripts/db/setup_db.ps1 como superusuario. Esta migración
la deja registrada en el historial y la crea si falta, cuando el usuario tiene
permisos (por ejemplo, en Docker).

Revision ID: 0001_postgis
Revises:
Create Date: 2026-11-12
"""

from alembic import op

revision = "0001_postgis"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # No se elimina PostGIS: otras tablas espaciales dependen de él
    pass
