import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { makeMe, renderApp, tule } from './helpers'

function navLinks() {
  const nav = screen.getAllByRole('navigation', { name: 'Navegación principal' })[0]
  return within(nav)
    .getAllByRole('link')
    .map((a) => a.textContent)
}

describe('Navegación y permisos por rol (HU-1.8)', () => {
  it.each([
    ['GERENCIA', ['Panel principal', 'Mapa', 'Embalses', 'Alertas', 'Reportes', 'Modelos de predicción', 'Datos satelitales', 'Usuarios', 'Bitácora', 'Ayuda', 'Estado del sistema']],
    ['INGENIERO', ['Panel principal', 'Mapa', 'Embalses', 'Registro diario', 'Importar datos', 'Alertas', 'Reportes', 'Modelos de predicción', 'Datos satelitales', 'Ayuda', 'Estado del sistema']],
    ['OPERADOR', ['Panel principal', 'Mapa', 'Embalses', 'Registro diario', 'Alertas', 'Ayuda', 'Estado del sistema']],
  ] as const)('el menú de %s muestra solo sus módulos', async (role, expected) => {
    renderApp('/', { 'GET /reservoirs': [tule] }, makeMe(role))
    await screen.findByRole('heading', { name: 'Tulé' })
    expect(navLinks()).toEqual(expected)
  })

  it('un Operador que entra a /importar es enviado al registro diario', async () => {
    renderApp('/importar', { 'GET /reservoirs': [tule] }, makeMe('OPERADOR'))
    expect(await screen.findByRole('heading', { name: 'Registro diario' })).toBeInTheDocument()
  })

  it('un Operador que escribe /usuarios en la barra vuelve al panel principal', async () => {
    renderApp('/usuarios', { 'GET /reservoirs': [tule] }, makeMe('OPERADOR'))
    expect(await screen.findByRole('heading', { name: 'Panel principal' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Usuarios' })).not.toBeInTheDocument()
  })

  it('sin embalses asignados muestra un mensaje que explica qué hacer', async () => {
    renderApp('/', { 'GET /reservoirs': [] }, makeMe('INGENIERO', { reservoir_codes: [] }))
    expect(await screen.findByText('No tienes embalses asignados')).toBeInTheDocument()
  })
})

describe('Ficha del embalse (HU-1.6, HU-1.7)', () => {
  const routes = { 'GET /reservoirs/TULE': tule, 'GET /reservoirs/TULE/curves': [] }

  it('el Ingeniero puede editar umbrales y cargar curvas', async () => {
    renderApp(
      '/embalses/TULE',
      {
        ...routes,
        'PUT /reservoirs/TULE/thresholds': (body) => ({ body: { ...(body as object), updated_at: null } }),
      },
      makeMe('INGENIERO'),
    )
    const field = await screen.findByLabelText('Nivel bajo de alerta')
    expect(field).toHaveValue('29')
    expect(field).toBeEnabled()
    expect(screen.getByRole('button', { name: /cargar nueva versión/i })).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Nivel bajo crítico'), '27,5')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar umbrales' }))
    expect(await screen.findByText('Umbrales guardados.')).toBeInTheDocument()
  })

  it('muestra el error de validación del servidor al guardar umbrales', async () => {
    renderApp(
      '/embalses/TULE',
      {
        ...routes,
        'PUT /reservoirs/TULE/thresholds': () => ({
          status: 422,
          body: { detail: [{ msg: 'Value error, El nivel de crítico bajo (30.0) debe ser menor que el de alerta baja (29.0).' }] },
        }),
      },
      makeMe('INGENIERO'),
    )
    await userEvent.type(await screen.findByLabelText('Nivel bajo crítico'), '30')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar umbrales' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('debe ser menor que el de alerta baja')
  })

  it('el Operador solo consulta', async () => {
    renderApp('/embalses/TULE', routes, makeMe('OPERADOR'))
    expect(await screen.findByLabelText('Nivel bajo de alerta')).toBeDisabled()
    expect(screen.getByText('Solo el Ingeniero puede modificar los umbrales.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /cargar nueva versión/i })).not.toBeInTheDocument()
  })
})

describe('Usuarios (HU-1.5)', () => {
  it('Gerencia crea un usuario y ve la contraseña temporal una sola vez', async () => {
    const created = {
      user: { ...makeMe('OPERADOR'), id: 9, full_name: 'Pedro Pérez', must_change_password: true },
      temporary_password: 'abcdEFGH-2345',
    }
    renderApp(
      '/usuarios',
      {
        'GET /users': { items: [], total: 0 },
        'GET /reservoirs': [tule],
        'POST /users': () => ({ status: 201, body: created }),
      },
      makeMe('GERENCIA'),
    )
    await userEvent.type(await screen.findByLabelText(/nombre completo/i), 'Pedro Pérez')
    await userEvent.type(screen.getByLabelText(/^correo/i), 'pedro@hidrica-zulia.com')
    await userEvent.click(screen.getByLabelText('Tulé'))
    await userEvent.click(screen.getByRole('button', { name: /crear usuario/i }))
    expect(await screen.findByText('abcdEFGH-2345')).toBeInTheDocument()
    expect(screen.getByText(/se muestra una sola vez/i)).toBeInTheDocument()
  })
})
