# Sistema de diseño

Definido en HU-0.4 con la skill `ui-ux-pro-max` (búsquedas `--design-system`, `--domain color` y `--domain typography`) y ajustado al contexto institucional. Los tokens viven en [frontend/src/index.css](../frontend/src/index.css) (`@theme` de Tailwind 4). **Los componentes usan solo tokens, nunca colores sueltos.**

## Decisiones

| Aspecto | Decisión | Motivo |
|---|---|---|
| Estilo | Minimalista / suizo, en modo claro primero | Lo recomienda la skill para paneles empresariales; los usuarios tienen nivel intermedio y trabajan en oficina. |
| Paleta | Azul marino institucional (`#0C4A6E`) + azul agua (`#0369A1`) | Combina las paletas "Government/Public Service" y "Water" de la skill. Se descartó la propuesta oscura con verde neón por ser demasiado "tech". |
| Tipografía | **Lexend** (títulos) + **Source Sans 3** (texto) | Es el par "Corporate Trust" de la skill, pensado para gobierno y accesibilidad. Se descartó Fira Code por ser una fuente de código. |
| Carga de fuentes | `@fontsource`, servidas desde el propio sitio | Sin Google Fonts: los servicios de Google no están disponibles en Venezuela (ver C-11). |
| Íconos | Phosphor (`@phosphor-icons/react`) | Es la recomendación de la skill: una sola familia, SVG y sin emojis. |

## Semáforo de embalses

Cada estado se muestra **siempre con color + ícono + texto**, nunca solo con color.

| Estado | Texto / borde | Fondo | Uso |
|---|---|---|---|
| Normal | `#15803D` | `#DCFCE7` | Cota dentro del rango operativo |
| Alerta | `#A16207` | `#FEF9C3` | Cerca de un umbral (bajo o alto) |
| Crítico / alivio | `#B91C1C` | `#FEE2E2` | Umbral crítico cruzado o embalse aliviando |
| Sin datos | `#475569` | `#E2E8F0` | Dato faltante o desactualizado |

Todos los pares de texto y fondo cumplen un contraste de al menos 4.5:1 (WCAG AA).

## Reglas aplicadas (de la skill)
- Enlace "Saltar al contenido", foco visible de 3 px y orden de tabulación natural.
- Botones de al menos 44 px de alto, `cursor-pointer` y estado deshabilitado mientras cargan.
- Mensajes de estado con `role="status"` y `aria-live="polite"`.
- Se respeta `prefers-reduced-motion`.
- Texto base de 16 px, interlineado de 1.5 y cifras tabulares en los datos.
- Diseño para móvil primero, con un ancho máximo de `max-w-6xl` y `min-h-dvh`.

## Pendiente para la Iteración 5
- Modo oscuro (tokens pares).
- Paleta de series para gráficos (ECharts), validada para daltonismo.
- Persistir el sistema con `--persist` en `design-system/` si crece.
