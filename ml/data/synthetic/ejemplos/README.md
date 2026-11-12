# ⚠️ Archivos de EJEMPLO sintéticos

Generados con `uv run python -m hidrica_ml.examples` a partir de `movimiento_diario_sintetico.csv` (fechas 2026-10-16 a 2026-10-31). No son mediciones de MINAGUAS.

| Archivo | Para qué sirve |
|---|---|
| `importacion_valida_2026-10-16_al_31.xlsx` | Importación correcta de 48 filas (3 embalses × 16 días) |
| `importacion_valida_formato_venezolano.csv` | Los mismos datos con `;`, coma decimal y fechas DD/MM/AAAA (como los exporta Excel en español) |
| `importacion_con_errores.xlsx` | Demostración del control de calidad: |
|   | • `DUPLICATE`: Fecha repetida (TULE 2026-10-20 aparece dos veces) |
|   | • `BAD_DATE`: Fecha imposible: 31/02/2026 |
|   | • `NOT_NUMERIC`: Cota escrita como texto: 'treinta' |
|   | • `MISSING`: Fila sin cota |
|   | • `NEGATIVE`: Caudal de salida negativo |
|   | • `OUT_OF_RANGE`: Apertura de compuertas 150 % |
|   | • `OUT_OF_CURVE`: Cota 5.00 m (fuera de la curva de Tulé, error de tipeo) |
|   | • `UNKNOWN_RESERVOIR`: Código de embalse mal escrito: 'TULEE' |
|   | • `FUTURE_DATE`: Fecha futura: 2030-01-01 |
|   | • `SUDDEN_JUMP`: Aviso: salto de +2,5 m en Manuelote el 2026-10-25 |
|   | • `MISSING_DAYS`: Aviso: faltan los días 2026-10-27 y 2026-10-28 de Tres Ríos |

Primero carga el histórico (hasta el 2026-10-15) con `uv run python -m app.cli load-synthetic-measurements` desde `backend/`, y luego importa estos archivos desde la plataforma (menú *Importar datos*).
