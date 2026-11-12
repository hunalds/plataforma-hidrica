// Localiza uv (en Windows, winget no siempre lo deja en el PATH de la sesión).
import { execSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

export function uvPath(): string {
  try {
    execSync('uv --version', { stdio: 'ignore' })
    return 'uv'
  } catch {
    const base = join(process.env.LOCALAPPDATA ?? '', 'Microsoft', 'WinGet', 'Packages')
    const dir = existsSync(base) ? readdirSync(base).find((d) => d.startsWith('astral-sh.uv')) : undefined
    if (dir) return `"${join(base, dir, 'uv.exe')}"`
    throw new Error('No se encontró uv. Instálalo con: winget install astral-sh.uv')
  }
}

export const backendCommand = (args: string) => `${uvPath()} ${args}`
