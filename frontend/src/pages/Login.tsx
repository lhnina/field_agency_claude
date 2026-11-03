import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ErrorBox, Field } from '../components/ui'
import logo from '../assets/argos-logo.png'
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
      </form>
      </div>
    </div>
  )
}
