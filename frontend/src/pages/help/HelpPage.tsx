import { BookOpen, MagnifyingGlass, Question, VideoCamera } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { useAuth } from '../../auth/AuthContext'
import { Card, PageHeader, TextField } from '../../components/ui'

// Glosario en lenguaje sencillo (M11). Mantener sincronizado con docs/manual-usuario.md.
const GLOSSARY: [string, string][] = [
  ['Cota', 'Altura del nivel del agua en metros sobre el nivel del mar (m.s.n.m.). Se lee cada día en el limnímetro o la regla.'],
  ['Limnímetro', 'Regla graduada instalada en el embalse para leer la cota.'],
  ['Volumen', 'Agua almacenada, en hectómetros cúbicos (1 hm³ = 1 millón de m³). Se calcula con la curva cota–volumen.'],
  ['Curva cota–área–volumen', 'Tabla que convierte la altura del agua en área del espejo y volumen almacenado. Tiene versiones con fecha de vigencia.'],
  ['Volumen muerto', 'Agua por debajo de la toma, que no se puede extraer.'],
  ['Volumen útil', 'Agua que sí se puede usar: volumen actual menos volumen muerto.'],
  ['Capacidad útil', 'Volumen útil cuando el embalse está en su nivel normal.'],
  ['Disponibilidad', 'Volumen útil como porcentaje de la capacidad útil. Más de 100 % significa que el embalse está aliviando.'],
  ['Días de reserva', 'Cuántos días alcanzaría el agua útil con la extracción y el gasto ecológico de hoy, sin lluvias.'],
  ['Nivel normal', 'Cota a partir de la cual el embalse empieza a aliviar (verter agua por el aliviadero).'],
  ['Alivio', 'Agua que el embalse vierte por el aliviadero cuando supera el nivel normal.'],
  ['Gasto ecológico', 'Caudal que se libera al río aguas abajo para mantener el ecosistema.'],
  ['Caudal', 'Volumen de agua que pasa por segundo (m³/s). Entrada = lo que aportan los ríos; salida = lo que se extrae hacia las plantas.'],
  ['Umbral', 'Cota de referencia que define el semáforo y las alertas: crítico bajo, alerta baja, alerta alta y alivio.'],
  ['Semáforo', 'Verde = normal; amarillo = alerta; rojo = crítico o aliviando; gris = sin datos recientes.'],
  ['Proyección', 'Estimación de la cota y el volumen para los próximos 90 días hecha con modelos de Machine Learning.'],
  ['Banda de incertidumbre', 'Rango donde se espera la cota real 8 de cada 10 veces. Más ancha = más incertidumbre.'],
  ['Backtesting', 'Prueba de los modelos sobre años pasados, como si se hubiera predicho en ese momento, para medir su error real.'],
  ['XGBoost', 'Modelo de Machine Learning basado en muchos árboles de decisión que aprende de las variables recientes.'],
  ['LSTM', 'Red neuronal que analiza los últimos 90 días como una secuencia para predecir la trayectoria.'],
  ['NDWI', 'Índice de agua calculado con imágenes satelitales (verde vs. infrarrojo cercano). Mayor que 0 indica agua.'],
  ['CHIRPS', 'Estimación de lluvia diaria por satélite y estaciones (Universidad de California). Se usa para la lluvia en la cuenca.'],
  ['ERA5-Land', 'Reanálisis climático del centro europeo ECMWF. Aporta la humedad del suelo.'],
  ['Sentinel-2 / Landsat', 'Satélites de observación de la Tierra (Europa / EE. UU.) usados para medir el espejo de agua.'],
  ['Área de influencia', 'Zona alrededor del embalse usada como aproximación de su cuenca mientras no se cargue la cuenca oficial.'],
]

const FAQ: [string, string][] = [
  ['¿Por qué el semáforo está gris?', 'Porque no hay mediciones recientes. Registra el movimiento del día en "Registro diario" o importa el archivo del período.'],
  ['¿Qué hago si me sale "Salto brusco"?', 'Revisa la lectura del limnímetro. Si es correcta (por ejemplo, una crecida), el dato se guarda igual y queda marcado para revisión.'],
  ['¿Cómo corrijo un registro?', 'El Operador puede corregir sus registros durante 24 horas desde la ficha; después debe pedirlo al Ingeniero. Toda corrección queda en la bitácora.'],
  ['¿Qué tan confiable es la proyección?', 'Cada modelo se probó con años pasados. En "Modelos de predicción" verás su error medio y cuántas veces el valor real cayó dentro de la banda.'],
  ['¿Por qué aparece "Datos sintéticos"?', 'Mientras llegan los históricos oficiales, la plataforma usa datos simulados para desarrollo. No representan mediciones reales de MINAGUAS.'],
  ['¿Quién recibe las alertas?', 'Todas aparecen en la plataforma. Además se envían por correo y Telegram a los destinatarios que configure el Ingeniero (SMS y WhatsApp quedan listos para conectar un proveedor).'],
  ['Olvidé mi contraseña', 'En la pantalla de inicio de sesión usa "¿Olvidaste tu contraseña?". Recibirás un enlace válido por 30 minutos. Gerencia también puede generarte una temporal.'],
  ['¿Puedo usar la plataforma en el teléfono?', 'Sí. Todas las pantallas se adaptan a teléfono, tableta y computadora.'],
]

const MANUAL: { role: string; steps: string[] }[] = [
  { role: 'Todos', steps: ['Inicia sesión con tu correo; la primera vez cambia la contraseña temporal.', 'El Panel principal muestra el semáforo, el mapa, las alertas activas y la disponibilidad comparada.', 'Toca un embalse para ver su estado, la proyección a 90 días, los indicadores satelitales y el movimiento diario.'] },
  { role: 'Operador', steps: ['Cada día entra a "Registro diario", elige el embalse, escribe la cota y los caudales y guarda.', 'Lee los avisos que muestra el sistema (por ejemplo, salto brusco) y verifica la lectura si hace falta.'] },
  { role: 'Ingeniero / Analista', steps: ['Define los umbrales y carga la curva cota–volumen en la ficha de cada embalse.', 'Importa históricos desde Excel/CSV en "Importar datos" revisando la vista previa.', 'Descarga datos satelitales, reentrena los modelos y configura los destinatarios de alertas.'] },
  { role: 'Gerencia', steps: ['Administra usuarios, roles y embalses asignados en "Usuarios".', 'Consulta la bitácora de auditoría y descarga los reportes (boletín diario, predicción, comparativos y alertas).'] },
]

export function HelpPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const terms = useMemo(() => GLOSSARY.filter(([t, d]) => `${t} ${d}`.toLowerCase().includes(q.toLowerCase())), [q])

  return (
    <div className="space-y-6">
      <PageHeader title="Ayuda" description="Manual rápido, preguntas frecuentes, videos y glosario de términos." />
      <Card>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <BookOpen size={22} aria-hidden="true" /> Manual rápido
        </h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          {MANUAL.filter((m) => m.role === 'Todos' || user?.role === 'GERENCIA' || m.role.toUpperCase().startsWith(user?.role ?? '-')).map((m) => (
            <section key={m.role}>
              <h3 className="font-heading font-semibold">{m.role}</h3>
              <ol className="mt-1 list-decimal space-y-1 pl-5">
                {m.steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
            </section>
          ))}
        </div>
        <p className="mt-3 text-sm text-muted-foreground">El manual de usuario completo está en la documentación del proyecto (docs/manual-usuario.md).</p>
      </Card>
      <Card>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <Question size={22} aria-hidden="true" /> Preguntas frecuentes
        </h2>
        <div className="mt-3 divide-y divide-border">
          {FAQ.map(([question, answer]) => (
            <details key={question} className="py-1">
              <summary className="min-h-11 cursor-pointer py-2 font-semibold">{question}</summary>
              <p className="pb-2 text-muted-foreground">{answer}</p>
            </details>
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <VideoCamera size={22} aria-hidden="true" /> Videos
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
          <li>Registro diario desde el teléfono (pendiente de grabación).</li>
          <li>Cómo leer la proyección y la banda de incertidumbre (pendiente de grabación).</li>
          <li>Importar el histórico desde Excel (pendiente de grabación).</li>
        </ul>
        <p className="mt-2 text-sm text-muted-foreground">Los videos se grabarán con la versión final; los enlaces se agregarán aquí.</p>
      </Card>
      <Card>
        <h2 className="text-xl font-semibold">Glosario</h2>
        <div className="mt-3 max-w-md">
          <TextField label="Buscar término" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <dl className="mt-4 grid gap-x-6 gap-y-3 md:grid-cols-2">
          {terms.map(([t, d]) => (
            <div key={t}>
              <dt className="font-semibold">{t}</dt>
              <dd className="text-muted-foreground">{d}</dd>
            </div>
          ))}
        </dl>
        {terms.length === 0 && (
          <p className="mt-3 flex items-center gap-2 text-muted-foreground">
            <MagnifyingGlass size={18} aria-hidden="true" /> Sin resultados para "{q}".
          </p>
        )}
      </Card>
      <p className="text-sm text-muted-foreground">
        ¿No encuentras lo que buscas? Revisa el <Link to="/estado" className="underline">estado del sistema</Link> o contacta al Ingeniero responsable.
      </p>
    </div>
  )
}
