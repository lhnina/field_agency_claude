const TOKEN_KEY = 'fa.token'
const USER_KEY = 'fa.user'

export type SessionUser = { id: number; nome: string; email: string; perfil: string; zona?: string | null }

export const session = {
  token: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  user: (): SessionUser | null => {
    try { const v = localStorage.getItem(USER_KEY); return v ? JSON.parse(v) : null } catch { return null }
  },
  set: (token: string, user: SessionUser) => {
    try { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch { /* sem storage */ }
  },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY) } catch { /* sem storage */ } },
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

function mensagem(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((e) => (e as { msg?: string }).msg?.replace(/^Value error, /, '') ?? '').join(' · ')
  }
  return `Erro ${status}`
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; params?: Record<string, unknown> } = {}): Promise<T> {
  const url = new URL('/api' + path, window.location.origin)
  Object.entries(opts.params ?? {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v)) })
  const headers: Record<string, string> = {}
  const t = session.token()
  if (t) headers.Authorization = `Bearer ${t}`
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  const r = await fetch(url, { method: opts.method ?? 'GET', headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined })
  if (r.status === 401 && path !== '/auth/login') {
    session.clear()
    window.location.assign('/login')
  }
  const body = r.status === 204 ? null : await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(r.status, mensagem(body, r.status))
  return body as T
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams({ username: email, password })
  const r = await fetch('/api/auth/login', { method: 'POST', body: form })
  const body = await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(r.status, mensagem(body, r.status))
  session.set(body.access_token, body.user)
  return body.user as SessionUser
}

/** Envio de formulário com ficheiro (multipart). */
export async function apiForm<T>(path: string, method: 'POST' | 'PUT', dados: Record<string, string | Blob | null | undefined>): Promise<T> {
  const fd = new FormData()
  Object.entries(dados).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') fd.append(k, v) })
  const headers: Record<string, string> = {}
  const t = session.token()
  if (t) headers.Authorization = `Bearer ${t}`
  const r = await fetch('/api' + path, { method, headers, body: fd })
  const body = await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(r.status, mensagem(body, r.status))
  return body as T
}

/** Abre um ficheiro protegido (com sessão) num novo separador. */
export async function abrirFicheiro(path: string) {
  const janela = window.open('', '_blank')
  const headers: Record<string, string> = {}
  const t = session.token()
  if (t) headers.Authorization = `Bearer ${t}`
  const r = await fetch('/api' + path, { headers })
  if (!r.ok) { janela?.close(); throw new ApiError(r.status, mensagem(await r.json().catch(() => null), r.status)) }
  const url = URL.createObjectURL(await r.blob())
  if (janela) janela.location.href = url
  else window.location.assign(url)
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
