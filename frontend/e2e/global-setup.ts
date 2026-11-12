// Siembra la base de PRUEBAS antes de las E2E: embalses, curvas e histórico sintéticos, geometrías y usuarios.
import { execSync } from 'node:child_process'

import { backendCommand } from './uv'

export const E2E_PASSWORD = 'E2e-Clave-2026'

export default function globalSetup() {
  const run = (args: string) =>
    execSync(backendCommand(`run python -m app.cli ${args}`), {
      cwd: '../backend',
      env: { ...process.env, APP_ENV: 'test' },
      stdio: 'inherit',
    })
  execSync(backendCommand('run alembic upgrade head'), { cwd: '../backend', env: { ...process.env, APP_ENV: 'test' }, stdio: 'inherit' })
  run('seed')
  run('load-synthetic-curves')
  run('load-synthetic-measurements --until 2026-10-15')
  run('load-geometries')
  for (const [email, role, res] of [
    ['e2e.gerencia@hidrica-zulia.com', 'GERENCIA', ''],
    ['e2e.operador@hidrica-zulia.com', 'OPERADOR', '--reservoirs TULE'],
  ]) {
    try {
      run(`create-user --email ${email} --name "E2E ${role}" --role ${role} --password ${E2E_PASSWORD} ${res}`)
    } catch {
      /* ya existe de una corrida anterior */
    }
  }
}
