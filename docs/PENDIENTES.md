# Pendientes por confirmar con MINAGUAS u otras fuentes

Cada valor de esta lista es **configurable** en el sistema. Mientras no se confirme, se usan valores marcados como provisionales o sintéticos.

## Datos y unidades
- [ ] **P-01** Unidades de las cotas de referencia (se asume m.s.n.m.).
- [ ] **P-02** Niveles de alerta y críticos (bajo y alto) de cada embalse. Por ahora no tienen valor y los configura el Ingeniero.
- [ ] **P-03** Curva cota–área–volumen vigente de cada embalse. La existente está desactualizada. Mientras tanto se usa una curva **sintética**.
- [ ] **P-04** Capacidad útil de cada embalse, en hm³.
- [ ] **P-05** Formato real de los históricos (Excel, SQL) y nombres de las columnas, para ajustar la plantilla de importación.
- [ ] **P-06** Acceso a la base SQL existente: motor, esquema y permisos de lectura.
- [ ] **P-19** Diferencia entre "caudal de salida/extracción" y "captación" en el registro diario. Hoy la plantilla los trata como columnas separadas y el dataset sintético les pone el mismo valor.
- [ ] **P-20** Hora oficial de la lectura diaria del limnímetro. El dataset sintético asume las 08:00.
- [ ] **P-21** Parámetros sintéticos de `ml/config/embalses.json` (volumen al nivel normal, cota de fondo, caudales medios): se deben reemplazar por los valores oficiales.

## Geometrías
- [ ] **P-07** Polígonos (GeoJSON) del espejo de agua de cada embalse.
- [ ] **P-08** Polígonos de las cuencas aportantes, para la precipitación y la humedad del suelo.

## Fórmulas del balance hídrico (M12), por validar
- [ ] **P-09** Volumen útil = volumen actual − volumen muerto.
- [ ] **P-10** Disponibilidad (%) = volumen útil / capacidad útil.
- [ ] **P-11** Días de reserva = volumen útil / (extracción diaria + gasto ecológico).
- [ ] **P-12** Alivio (hm³) cuando la cota supera el nivel normal: hace falta el método oficial (curva del aliviadero o diferencia de volumen).
- [ ] **P-13** Balance diario = entradas − salidas − gasto ecológico − alivio, frente al cambio de volumen observado. Falta la tolerancia aceptada.

## Satélite
- [ ] **P-14** Confirmar desde la **red de MINAGUAS** el acceso a CHIRPS, Copernicus y Planetary Computer. Desde la red de los autores ya funcionan todas (ver `docs/evidencias/HU-0.6-fuentes-satelitales.md`).
- [ ] **P-15** Producto de humedad del suelo: ERA5-Land (0,1°) o SMAP (9 km, desde 2015). Justificar la elección en la tesis.

## Seguridad (validar con la institución)
- [ ] **P-22** Dónde guardar el token de renovación en el navegador. Hoy está en `localStorage`; en producción conviene una cookie `httpOnly`, pero hay que confirmar los dominios del frontend y del backend (Iteración 7).
- [ ] **P-23** Política de contraseñas y parámetros de bloqueo (10 caracteres, 5 intentos, 15 min, sesión inactiva 30 min). Revisar si las normativas institucionales piden otros valores.
- [ ] **P-24** Proveedor SMTP oficial para el envío de correos (recuperación y alertas).

## Institucional
- [ ] **P-16** Normativas institucionales sobre el almacenamiento de datos: dónde deben residir los datos y por cuánto tiempo se retienen.
- [ ] **P-17** Proveedor de SMS y WhatsApp para las alertas.
- [ ] **P-18** Destinatarios oficiales de las alertas y sus canales (Ministro, Viceministro, Director Estadal).
