# Herramientas de IA usadas en el desarrollo

El desarrollo se asiste con Claude Code. Las skills de terceros **no se versionan** en Git porque pesan unos 39 MB; se reinstalan con las instrucciones de este documento.

## Instaladas en el proyecto (`.claude/`)

| Herramienta | Tipo | Origen | Uso en el proyecto |
|---|---|---|---|
| `design-taste-frontend` | Skill | https://github.com/leonxlnx/taste-skill (`skills/taste-skill`) | Página de inicio de sesión, portada y pulido visual |
| `data-scientist` | Subagente | https://github.com/VoltAgent/awesome-claude-code-subagents (`categories/05-data-ai/data-scientist.md`) | Análisis exploratorio, revisión de features y backtesting |
| `chirps-fetch`, `arco-era5-fetch`, `smap-fetch`, `clip-region`, `aggregate-temporal`, `unit-convert`, `csv-io`, `verify`, `provenance`, `inspect-zarr` | Skills | https://github.com/rhiza-research/weather-skills (`skills/`) | Prototipado de la ingesta de precipitación y humedad del suelo |

## Global (perfil del usuario)
| Herramienta | Tipo | Origen | Uso en el proyecto |
|---|---|---|---|
| `ui-ux-pro-max` | Skill | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | Diseño del panel, accesibilidad y paleta |

## Reinstalación (Git Bash)

```bash
TMP=$(mktemp -d); cd "$TMP"
git clone --depth 1 https://github.com/leonxlnx/taste-skill
git clone --depth 1 https://github.com/rhiza-research/weather-skills
git clone --depth 1 https://github.com/VoltAgent/awesome-claude-code-subagents
P=/ruta/a/plataforma-hidrica
mkdir -p "$P/.claude/skills" "$P/.claude/agents"
cp -r taste-skill/skills/taste-skill "$P/.claude/skills/design-taste-frontend"
cp awesome-claude-code-subagents/categories/05-data-ai/data-scientist.md "$P/.claude/agents/"
for s in chirps-fetch arco-era5-fetch smap-fetch clip-region aggregate-temporal unit-convert csv-io verify provenance inspect-zarr; do
  cp -r "weather-skills/skills/$s" "$P/.claude/skills/$s"
done
```

## Requisitos
- Las weather-skills necesitan `uv` y Python 3.12. Se ejecutan con `uv run <skill>/scripts/<script>.py`.
- `design-taste-frontend` necesita Node 22+ y Chrome o Edge. Agrega una verificación automática (`gate.mjs`) al final de cada respuesta de Claude, que solo actúa si existe la carpeta `.taste-skill/`.

## Notas de seguridad
Antes de instalarlas se revisó el contenido de las tres fuentes (2026-11-11). Los scripts solo acceden a catálogos públicos de datos (dynamical.org, ARCO-ERA5 y NASA Earthdata) y no ejecutan comandos del sistema.
