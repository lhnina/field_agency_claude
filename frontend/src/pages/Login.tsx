import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ErrorBox, Field, Icon } from '../components/ui'
import { login } from '../lib/api'

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
    <div className="min-h-screen grid place-items-center bg-bg p-6">
      <form onSubmit={submit} className="card w-full max-w-[400px] p-7 flex flex-col gap-4">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-9 h-9 rounded-[10px] bg-amber-400 grid place-items-center text-petrol-900"><Icon name="cal" strokeWidth={2.2} /></div>
          <div><div className="text-lg font-semibold leading-tight">Field Agency</div><div className="text-[12.5px] text-ink-60">Gestão operacional</div></div>
        </div>
        <Field label="Email">{(id) => <input id={id} className="inp" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />}</Field>
        <Field label="Palavra-passe">{(id) => <input id={id} className="inp" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required />}</Field>
        {err ? <ErrorBox error={err} /> : null}
        <Button variant="primary" type="submit" loading={busy} className="mt-1">Entrar</Button>
      </form>
    </div>
  )
}
