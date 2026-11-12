import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { makeMe, renderApp, tokenResponse, tule } from './helpers'

describe('Autenticación (HU-1.1 a HU-1.3, HU-1.8)', () => {
  it('sin sesión, cualquier ruta protegida lleva al inicio de sesión', async () => {
    renderApp('/usuarios')
    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument()
  })

  it('inicia sesión y muestra los embalses', async () => {
    const { fetchSpy } = renderApp('/login', {
      'POST /auth/login': tokenResponse(makeMe('OPERADOR')),
      'GET /reservoirs': [tule],
    })
    await userEvent.type(await screen.findByLabelText(/correo/i), 'operador@hidrica-zulia.com')
    await userEvent.type(screen.getByLabelText(/^contraseña/i), 'Clave-Segura-2026')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('heading', { name: 'Tulé' })).toBeInTheDocument()
    const loginCall = fetchSpy.mock.calls.find(([url]) => String(url).endsWith('/auth/login'))
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({
      email: 'operador@hidrica-zulia.com',
      password: 'Clave-Segura-2026',
    })
  })

  it('muestra el mensaje del servidor si las credenciales son incorrectas o la cuenta está bloqueada', async () => {
    renderApp('/login', {
      'POST /auth/login': () => ({
        status: 423,
        body: { detail: { code: 'ACCOUNT_LOCKED', message: 'Cuenta bloqueada temporalmente. Intenta de nuevo en 15 minutos.' } },
      }),
    })
    await userEvent.type(await screen.findByLabelText(/correo/i), 'a@hidrica-zulia.com')
    await userEvent.type(screen.getByLabelText(/^contraseña/i), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cuenta bloqueada temporalmente')
  })

  it('el botón del ojo muestra y oculta la contraseña', async () => {
    renderApp('/login')
    const input = await screen.findByLabelText(/^contraseña/i)
    expect(input).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(input).toHaveAttribute('type', 'text')
  })

  it('en el primer acceso obliga a cambiar la contraseña antes de continuar', async () => {
    const first = makeMe('INGENIERO', { must_change_password: true })
    renderApp(
      '/',
      {
        'POST /auth/change-password': tokenResponse(makeMe('INGENIERO')),
        'GET /reservoirs': [tule],
      },
      first,
    )
    expect(await screen.findByRole('heading', { name: 'Cambia tu contraseña' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/actual/i), 'Temporal-1234')
    await userEvent.type(screen.getByLabelText(/^nueva contraseña/i), 'Nueva-Clave-2027')
    await userEvent.type(screen.getByLabelText(/repite/i), 'Otra-Clave-2027')
    expect(screen.getByText('Las contraseñas no coinciden.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cambiar contraseña' })).toBeDisabled()

    await userEvent.clear(screen.getByLabelText(/repite/i))
    await userEvent.type(screen.getByLabelText(/repite/i), 'Nueva-Clave-2027')
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))
    expect(await screen.findByRole('heading', { name: 'Tulé' })).toBeInTheDocument()
  })

  it('recuperación: solicita el enlace y luego restablece con el token', async () => {
    renderApp('/recuperar', {
      'POST /auth/forgot-password': { message: 'Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.' },
    })
    await userEvent.type(await screen.findByLabelText(/correo/i), 'a@hidrica-zulia.com')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar enlace' }))
    expect(await screen.findByText(/recibirás un enlace/)).toBeInTheDocument()
  })

  it('restablecer con token válido', async () => {
    const { fetchSpy } = renderApp('/restablecer?token=abc123token', {
      'POST /auth/reset-password': { message: 'Tu contraseña fue restablecida. Ya puedes iniciar sesión.' },
    })
    await userEvent.type(await screen.findByLabelText(/^nueva contraseña/i), 'Recuperada-2026')
    await userEvent.type(screen.getByLabelText(/repite/i), 'Recuperada-2026')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))
    expect(await screen.findByText(/restablecida/)).toBeInTheDocument()
    const call = fetchSpy.mock.calls.find(([url]) => String(url).endsWith('/auth/reset-password'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ token: 'abc123token', new_password: 'Recuperada-2026' })
  })

  it('si el token de acceso vence, renueva la sesión y repite la petición', async () => {
    let calls = 0
    renderApp(
      '/',
      {
        'GET /reservoirs': () => {
          calls += 1
          return calls === 1
            ? { status: 401, body: { detail: { code: 'NOT_AUTHENTICATED', message: 'expiró' } } }
            : { body: [tule] }
        },
      },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByRole('heading', { name: 'Tulé' })).toBeInTheDocument()
    expect(calls).toBe(2)
  })

  it('cerrar sesión vuelve al inicio de sesión', async () => {
    renderApp('/', { 'GET /reservoirs': [tule], 'POST /auth/logout': { message: 'ok' } }, makeMe('OPERADOR'))
    await screen.findByRole('heading', { name: 'Tulé' })
    const header = screen.getByRole('banner')
    await userEvent.click(within(header).getByRole('button', { name: /cerrar sesión/i }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument())
  })
})
