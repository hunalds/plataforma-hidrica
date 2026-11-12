# Plataforma Hídrica Zulia

Plataforma web con Machine Learning y datos satelitales para predecir la disponibilidad hídrica de los embalses **Tulé, Manuelote y Tres Ríos** (estado Zulia, Venezuela).

Tesis de Ingeniería en Informática, Universidad Privada Dr. Rafael Belloso Chacín (URBE).
Autores: Hunaldo Hernández y Angie Rubistein. Tutores: Miguel Vílchez y Maribel Ordóñez.

> ⚠️ Los datos de `ml/data/synthetic/` son **sintéticos** y solo sirven para el desarrollo. No representan mediciones reales de MINAGUAS.

## Estado
En desarrollo, Iteración 0 (Exploración). Ver [docs/historias-de-usuario.md](docs/historias-de-usuario.md).

## Documentación
- [CLAUDE.md](CLAUDE.md): decisiones del proyecto y forma de trabajo
- [docs/CAMBIOS-PROMPT.md](docs/CAMBIOS-PROMPT.md): cambios respecto a los requerimientos originales
- [docs/PENDIENTES.md](docs/PENDIENTES.md): datos y fórmulas por confirmar con MINAGUAS
- [docs/herramientas-ia.md](docs/herramientas-ia.md): herramientas de IA usadas en el desarrollo

## Requisitos de desarrollo
- Python 3.12 (gestionado con [uv](https://docs.astral.sh/uv/))
- Node.js 22+
- PostgreSQL 18 + PostGIS
