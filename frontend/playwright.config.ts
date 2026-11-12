// Pruebas E2E (Iteración 7): backend real (APP_ENV=test → base plataforma_hidrica_test) + frontend real.
// Uso: npx playwright test   (no correr a la vez que pytest: ambos usan la base de pruebas)
import { defineConfig, devices } from '@playwright/test'

import { backendCommand } from './e2e/uv'

const API_PORT = 8010
const WEB_PORT = 5180

export default defineConfig({
  testDir: './e2e',
  // Las capturas de la tesis entrenan modelos y escriben en docs/: solo con CAPTURAS=1
  testIgnore: process.env.CAPTURAS ? [] : ['**/capturas.spec.ts'],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    locale: 'es-VE',
    timezoneId: 'America/Caracas',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'escritorio', use: { ...devices['Desktop Chrome'] } },
    { name: 'telefono', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: backendCommand(`run uvicorn app.main:app --port ${API_PORT}`),
      cwd: '../backend',
      url: `http://localhost:${API_PORT}/health`,
      env: { APP_ENV: 'test', CORS_ORIGINS: `http://localhost:${WEB_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { VITE_API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
