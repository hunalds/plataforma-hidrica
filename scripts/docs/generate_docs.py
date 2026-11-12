"""Genera documentación técnica a partir del código (M11):

- docs/diccionario-datos.md: tablas, columnas, tipos, nulos, claves y descripciones, desde los modelos SQLAlchemy.
- docs/api/openapi.json y docs/api/endpoints.md: especificación OpenAPI de FastAPI y su índice legible.

Uso (desde backend/):  PYTHONPATH=. uv run python ../scripts/docs/generate_docs.py
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import Enum as SAEnum

import app.models as models_pkg
from app.main import create_app
from app.core.config import Settings
from app.models import Base

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def column_comments(model) -> dict[str, str]:
    """Comentario en línea (# ...) junto a cada columna en el código fuente del modelo."""
    src = inspect.getsource(model)
    out = {}
    for line in src.splitlines():
        stripped = line.strip()
        if ":" in stripped and "mapped_column" in stripped and "#" in stripped:
            name = stripped.split(":")[0].strip()
            out[name] = stripped.split("#", 1)[1].strip()
    return out


def class_doc(model) -> str:
    doc = inspect.getdoc(model) or ""
    return " ".join(doc.split())


def data_dictionary() -> str:
    mappers = {m.class_.__tablename__: m.class_ for m in Base.registry.mappers}
    lines = [
        "# Diccionario de datos",
        "",
        f"Generado automáticamente desde los modelos SQLAlchemy el {date.today().isoformat()} "
        "(`scripts/docs/generate_docs.py`). Base de datos: PostgreSQL 18 + PostGIS. Esquema migrado con Alembic.",
        "",
        "Convenciones: cotas en m.s.n.m., volúmenes en hm³, caudales en m³/s (media diaria), fechas en hora de Caracas.",
        "",
        "## Índice",
        "",
    ]
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    lines += [f"- [`{t.name}`](#{t.name.replace('_', '-')})" for t in tables]
    for t in tables:
        model = mappers.get(t.name)
        comments = column_comments(model) if model else {}
        lines += ["", f"## {t.name}", ""]
        if model:
            lines += [class_doc(model) or "—", ""]
        lines += ["| Columna | Tipo | Nulo | Clave | Descripción |", "|---|---|---|---|---|"]
        for c in t.columns:
            ctype = c.type
            if isinstance(ctype, SAEnum):
                type_s = "ENUM(" + ", ".join(ctype.enums) + ")"
            else:
                try:
                    type_s = str(ctype.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
                except Exception:  # noqa: BLE001
                    type_s = type(ctype).__name__
            keys = []
            if c.primary_key:
                keys.append("PK")
            for fk in c.foreign_keys:
                keys.append(f"FK → {fk.target_fullname}")
            if c.unique:
                keys.append("único")
            lines.append(f"| `{c.name}` | {type_s} | {'sí' if c.nullable else 'no'} | {', '.join(keys) or '—'} | {comments.get(c.name, '—')} |")
        uniques = [u for u in t.constraints if u.__class__.__name__ == "UniqueConstraint" and len(u.columns) > 1]
        for u in uniques:
            lines.append(f"\nRestricción de unicidad: ({', '.join(col.name for col in u.columns)}).")
    return "\n".join(lines) + "\n"


def api_docs() -> tuple[str, str]:
    app = create_app(Settings(app_env="test"))
    spec = app.openapi()
    lines = [
        "# API REST · índice de endpoints",
        "",
        f"Generado el {date.today().isoformat()} desde FastAPI. Especificación completa: [openapi.json](openapi.json). "
        "Documentación interactiva en el servidor: `/docs` (Swagger) y `/redoc`.",
        "",
        "Autenticación: `Authorization: Bearer <token de acceso>` (ver `/auth/login`). Errores: `{\"detail\": {\"code\", \"message\"}}`.",
        "",
    ]
    by_tag: dict[str, list[tuple[str, str, str]]] = {}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            by_tag.setdefault((op.get("tags") or ["otros"])[0], []).append((method.upper(), path, op.get("summary", "")))
    for tag in sorted(by_tag):
        lines += [f"## {tag.capitalize()}", "", "| Método | Ruta | Descripción |", "|---|---|---|"]
        lines += [f"| {m} | `{p}` | {s} |" for m, p, s in sorted(by_tag[tag], key=lambda x: (x[1], x[0]))]
        lines.append("")
    return json.dumps(spec, ensure_ascii=False, indent=2), "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    _ = models_pkg, ast  # todos los modelos importados (registro completo)
    (DOCS / "api").mkdir(parents=True, exist_ok=True)
    (DOCS / "diccionario-datos.md").write_text(data_dictionary(), encoding="utf-8")
    spec, index = api_docs()
    (DOCS / "api" / "openapi.json").write_text(spec, encoding="utf-8")
    (DOCS / "api" / "endpoints.md").write_text(index, encoding="utf-8")
    print("Generados: docs/diccionario-datos.md, docs/api/openapi.json, docs/api/endpoints.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
