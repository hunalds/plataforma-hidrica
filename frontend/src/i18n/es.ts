// Textos de la interfaz en español (Venezuela). Centralizados para mantener un lenguaje sencillo y consistente.
export const es = {
  app: {
    name: 'Plataforma Hídrica Zulia',
    subtitle: 'Predicción de disponibilidad hídrica · Embalses Tulé, Manuelote y Tres Ríos',
    skipToContent: 'Saltar al contenido principal',
    footer: 'Proyecto de tesis · URBE · Datos en desarrollo (sintéticos)',
  },
  status: {
    title: 'Estado del sistema',
    intro: 'Comprueba que la plataforma puede comunicarse con el servidor y con la base de datos.',
    checking: 'Verificando conexión…',
    connected: 'API conectada',
    disconnected: 'Sin conexión con la API',
    disconnectedHelp:
      'No se pudo contactar al servidor. Verifica que el backend esté encendido e inténtalo de nuevo.',
    degraded: 'API activa, base de datos no disponible',
    retry: 'Reintentar',
    database: 'Base de datos',
    postgis: 'PostGIS (datos geográficos)',
    version: 'Versión de la API',
    environment: 'Entorno',
    lastCheck: 'Última verificación',
    ok: 'Funcionando',
    error: 'Con fallas',
  },
  notFound: {
    title: 'Página no encontrada',
    body: 'La dirección que buscas no existe.',
    back: 'Volver al inicio',
  },
} as const
