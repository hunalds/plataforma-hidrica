// Capturas de pantalla de cada módulo para la tesis (Capítulo IV y manual de usuario).
// Uso (PowerShell): $env:CAPTURAS=1; npx playwright test e2e/capturas.spec.ts --project=escritorio
// Las imágenes se guardan en ../docs/capturas/ (datos SINTÉTICOS de la base de pruebas).
import { execSync } from 'node:child_process'

import { expect, test, type Page } from '@playwright/test'

import { backendCommand } from './uv'

const PASSWORD = 'E2e-Clave-2026'
const OUT = '../docs/capturas'

test.describe.configure({ mode: 'serial' })
// eslint-disable-next-line no-empty-pattern
test.beforeAll(({}, workerInfo) => {
  test.skip(workerInfo.project.name !== 'escritorio', 'Solo en escritorio')
  const run = (args: string) =>
    execSync(backendCommand(`run python -m app.cli ${args}`), { cwd: '../backend', env: { ...process.env, APP_ENV: 'test' }, stdio: 'inherit' })
  run('load-synthetic-satellite')
  run('train-models --kinds persistencia estacional --test-years 2025')
  for (const [email, role, res] of [
    ['e2e.ingeniero@hidrica-zulia.com', 'INGENIERO', '--reservoirs TULE MANUELOTE TRES_RIOS'],
  ]) {
    try {
      run(`create-user --email ${email} --name "Ingeniera de prueba" --role ${role} --password ${PASSWORD} ${res}`)
    } catch {
      /* ya existe */
    }
  }
})

async function login(page: Page, email: string) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  await page.getByLabel(/correo/i).fill(email)
  await page.getByLabel(/^contraseña/i).fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Panel principal' })).toBeVisible()
}

async function shot(page: Page, name: string, fullPage = true) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800) // gráficas y mosaicos del mapa
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage })
}

test('capturas del Ingeniero', async ({ page }) => {
  test.setTimeout(300_000)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  await shot(page, 'm1-inicio-sesion', false)
  await login(page, 'e2e.ingeniero@hidrica-zulia.com')
  await page.goto('/alertas')
  const evaluate = page.getByRole('button', { name: /evaluar ahora/i })
  await evaluate.click()
  await expect(page.getByText(/Evaluación terminada/)).toBeVisible({ timeout: 60_000 })
  await shot(page, 'm9-alertas')
  await page.goto('/')
  await shot(page, 'm7-panel-principal')
  await page.goto('/mapa')
  await shot(page, 'm8-mapa', false)
  await page.goto('/embalses/TULE')
  await expect(page.getByRole('heading', { name: 'Proyección a 90 días' })).toBeVisible({ timeout: 30_000 })
  await shot(page, 'm6-m12-ficha-embalse-proyeccion')
  await page.goto('/registro')
  await shot(page, 'm4-registro-diario')
  await page.goto('/importar')
  await page.getByLabel(/archivo \(\.xlsx o \.csv\)/i).setInputFiles('../ml/data/synthetic/ejemplos/importacion_con_errores.xlsx')
  await page.getByRole('button', { name: /revisar archivo/i }).click()
  await expect(page.getByText(/Revisa la vista previa/)).toBeVisible({ timeout: 30_000 })
  await shot(page, 'm4-importacion-control-calidad')
  await page.goto('/modelos')
  await shot(page, 'm6-modelos-prediccion')
  await page.goto('/satelite')
  await shot(page, 'm5-datos-satelitales')
  await page.goto('/reportes')
  await shot(page, 'm10-reportes')
  await page.goto('/ayuda')
  await shot(page, 'm11-ayuda')
})

test('capturas de Gerencia', async ({ page }) => {
  await login(page, 'e2e.gerencia@hidrica-zulia.com')
  await page.goto('/usuarios')
  await shot(page, 'm2-usuarios')
  await page.goto('/auditoria')
  await shot(page, 'm1-bitacora-auditoria')
})

test('captura en teléfono', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.getByLabel(/correo/i).fill('e2e.operador@hidrica-zulia.com')
  await page.getByLabel(/^contraseña/i).fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Panel principal' })).toBeVisible()
  await shot(page, 'responsive-telefono-panel')
  await page.goto('/registro')
  await shot(page, 'responsive-telefono-registro')
})
