// Flujos principales de punta a punta (navegador real + API real + PostgreSQL de pruebas).
import { expect, test, type Page } from '@playwright/test'

const PASSWORD = 'E2e-Clave-2026'

async function login(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel(/correo/i).fill(email)
  await page.getByLabel(/^contraseña/i).fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Panel principal' })).toBeVisible()
}

test('Gerencia: panel con semáforo, mapa y ficha con indicadores', async ({ page }) => {
  await login(page, 'e2e.gerencia@hidrica-zulia.com')
  for (const name of ['Tulé', 'Manuelote', 'Tres Ríos']) {
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
  }
  await expect(page.getByText('Lluvia de 30 días')).toBeVisible()
  await page.getByRole('heading', { name: 'Tulé', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Embalse Tulé' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Estado actual' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Movimiento diario' })).toBeVisible()
  await page.screenshot({ path: 'test-results/capturas/ficha-tule.png', fullPage: true })
})

test('Gerencia descarga el boletín diario en Excel', async ({ page }) => {
  await login(page, 'e2e.gerencia@hidrica-zulia.com')
  await page.goto('/reportes')
  const card = page.locator('section', { has: page.getByRole('heading', { name: 'Boletín diario' }) })
  const download = page.waitForEvent('download')
  await card.getByRole('button', { name: /Excel/ }).click()
  expect((await download).suggestedFilename()).toMatch(/^boletin_.*\.xlsx$/)
})

test('Operador: registra la lectura del día y no ve módulos ajenos', async ({ page }) => {
  await login(page, 'e2e.operador@hidrica-zulia.com')
  const nav = page.getByRole('navigation', { name: 'Navegación principal' }).first()
  if (await page.getByRole('button', { name: 'Abrir menú' }).isVisible()) await page.getByRole('button', { name: 'Abrir menú' }).click()
  await expect(nav.getByRole('link', { name: 'Usuarios' })).toHaveCount(0)
  await page.goto('/registro')
  await page.getByLabel(/^Cota/).fill('29,35')
  await page.getByLabel(/^Caudal de salida/).fill('4,1')
  await page.getByRole('button', { name: /guardar registro/i }).click()
  await expect(page.getByText(/guardado \(Tulé\)|Ya existe un registro/)).toBeVisible()
})

test('Inicio de sesión rechaza credenciales incorrectas', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel(/correo/i).fill('e2e.gerencia@hidrica-zulia.com')
  await page.getByLabel(/^contraseña/i).fill('incorrecta-123')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('alert')).toContainText('Correo o contraseña incorrectos')
})
