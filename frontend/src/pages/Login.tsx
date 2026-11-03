import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ErrorBox, Field } from '../components/ui'
import logo from '../assets/argos-logo.png'
import { login } from '../lib/api'

// Atalhos de demonstração: preenchem o email e a palavra-passe dos utilizadores criados pelo seed.
// Aparecem em modo de desenvolvimento ou quando VITE_DEMO=1.
const DEMO = import.meta.env.DEV || import.meta.env.VITE_DEMO === '1'
const PERFIS_DEMO = [
  { perfil: 'Administrador', nome: 'Administrador', email: 'admin@promovida.pt' },
  { perfil: 'Direção', nome: 'Marta Ribeiro', email: 'marta@promovida.pt' },
  { perfil: 'Gestor operacional', nome: 'Hugo Faria', email: 'hugo@promovida.pt' },
  { perfil: 'Supervisor', nome: 'Rui Matos', email: 'rui@promovida.pt' },
  { perfil: 'Supervisor', nome: 'Sara Guedes', email: 'sara@promovida.pt' },
]

export default function Login() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { await login(email, pw); nav('/') } catch (x) { setErr(x) } finally { setBusy(false) }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-petrol-900 p-6">
      <div className="w-full max-w-[400px] flex flex-col items-center gap-6">
      <div className="flex flex-col items-center gap-3">
        <img src={logo} alt="Argos" className="h-40 w-auto" />
        <div className="text-[13px] text-[#93AAA6]">Gestão operacional de agências de field marketing</div>
      </div>
      <form onSubmit={submit} className="card w-full p-7 flex flex-col gap-4">
        <Field label="Email">{(id) => <input id={id} className="inp" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />}</Field>
        <Field label="Palavra-passe">{(id) => <input id={id} className="inp" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required />}</Field>
        {err ? <ErrorBox error={err} /> : null}
        <Button variant="primary" type="submit" loading={busy} className="mt-1">Entrar</Button>
        {DEMO && (
          <div className="border-t border-line pt-3.5 -mx-7 px-7">
            <div className="text-xs text-ink-60 mb-2">Entrar como (demonstração)</div>
            <div className="flex flex-col">
              {PERFIS_DEMO.map((u) => (
                <button key={u.email} type="button" onClick={() => { setEmail(u.email); setPw('demo1234'); setErr(null) }}
                  className={`flex items-center justify-between gap-3 text-left px-2 py-1.5 -mx-2 rounded-md hover:bg-petrol-50 ${email === u.email ? 'bg-petrol-50' : ''}`}>
                  <span className="text-[13px] text-petrol-600 font-medium">{u.perfil}</span>
                  <span className="text-xs text-ink-60">{u.nome} · {u.email}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
      </div>
    </div>
  )
}
