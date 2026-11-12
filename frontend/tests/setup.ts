import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom reemplaza AbortSignal, pero Request es el de Node (undici) y rechaza esa señal.
// React Router crea un Request con `signal` en cada navegación: en pruebas se omite la señal.
const NodeRequest = globalThis.Request
class TestRequest extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const rest: RequestInit = { ...init }
    delete rest.signal
    super(input, rest)
  }
}
globalThis.Request = TestRequest as typeof Request

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})
