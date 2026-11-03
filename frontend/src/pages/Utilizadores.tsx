import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Icon, Loading, Modal, useToast } from '../components/ui'
import { api, session } from '../lib/api'

type U = { id: number; nome: string; email: string; perfil: string; ativo: boolean }
export const PERFIS: Record<string, { label: string; desc: string }> = {
  administrador: { label: 'Administrador', desc: 'Acesso total, incluindo utilizadores e configuração' },
  direcao: { label: 'Direção', desc: 'Consulta tudo, fecha e reabre períodos, configuração' },
  gestor: { label: 'Gestor operacional', desc: 'Contratos, planeamento, validação, importação' },
  supervisor: { label: 'Supervisor', desc: 'Planeamento, ausências e validação só da sua equipa' },
  rh: { label: 'Recursos humanos', desc: 'Colaboradores, ausências, apuramento de remunerações' },
  financeiro: { label: 'Financeiro', desc: 'Pré-faturação, apuramento, fecho de períodos' },
}

export default function Utilizadores() {
  const q = useQuery({ queryKey: ['utilizadores'], queryFn: () => api<U[]>('/utilizadores') })
  const [edit, setEdit] = useState<U | 'novo' | null>(null)
  const [senha, setSenha] = useState<U | null>(null)
  const eu = session.user()
  if (q.isLoading) return <Card><Loading /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 px-[18px] py-3 border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Utilizadores</h3>
          <span className="text-[12.5px] text-ink-60">{q.data?.filter((u) => u.ativo).length} ativos</span>
          <span className="flex-1" />
          <Button size="sm" variant="primary" icon="plus" onClick={() => setEdit('novo')}>Novo utilizador</Button>
        </div>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Nome</th><th>Email</th><th>Perfil</th><th>Estado</th><th /></tr></thead>
            <tbody>{q.data?.map((u) => (
              <tr key={u.id} className={u.ativo ? '' : 'opacity-60'}>
                <td><div className="flex items-center gap-2.5"><Avatar nome={u.nome} /><span className="font-medium">{u.nome}{u.id === eu?.id && <span className="text-xs text-ink-60 font-normal"> (você)</span>}</span></div></td>
                <td className="text-[12.5px]">{u.email}</td>
                <td>{PERFIS[u.perfil]?.label ?? u.perfil}</td>
                <td>{u.ativo ? <Badge tone="ok" dot>Ativo</Badge> : <Badge dot>Inativo</Badge>}</td>
                <td className="text-right whitespace-nowrap">
                  <Button size="sm" variant="ghost" icon="edit" onClick={() => setEdit(u)}>Editar</Button>
                  <Button size="sm" variant="ghost" onClick={() => setSenha(u)}>Repor palavra-passe</Button>
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
      <p className="text-[12.5px] text-ink-60 flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />
        Os supervisores ficam disponíveis para associar a lojas e colaboradores. Desativar um utilizador impede-o de entrar, mas mantém o histórico.</p>
      {edit && <UtilizadorDialog u={edit === 'novo' ? null : edit} onClose={() => setEdit(null)} />}
      {senha && <SenhaDialog u={senha} onClose={() => setSenha(null)} />}
    </>
  )
}

const senhaErro = (v: string) => (v && (v.length < 8 || /^[^0-9]*$/.test(v) || /^[0-9]*$/.test(v)) ? 'Mínimo 8 caracteres, com letras e números' : null)

function UtilizadorDialog({ u, onClose }: { u: U | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const admin = session.user()?.perfil === 'administrador'
  const [f, setF] = useState({ nome: u?.nome ?? '', email: u?.email ?? '', perfil: u?.perfil ?? 'supervisor', ativo: u?.ativo ?? true, password: '' })
  const m = useMutation({
    mutationFn: () => api(u ? `/utilizadores/${u.id}` : '/utilizadores', { method: u ? 'PUT' : 'POST', body: u ? { ...f, password: undefined } : f }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['utilizadores'] }); qc.invalidateQueries({ queryKey: ['supervisores'] })
      toast(u ? 'Utilizador atualizado' : 'Utilizador criado. Comunique-lhe a palavra-passe temporária.'); onClose()
    },
  })
  const pe = u ? null : senhaErro(f.password)
  return (
    <Modal title={u ? `Editar ${u.nome}` : 'Novo utilizador'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="primary" loading={m.isPending} disabled={!f.nome || !f.email || (!u && (!f.password || !!pe))} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Nome">{(id) => <input id={id} className="inp" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Field>
        <Field label="Email (para entrar)">{(id) => <input id={id} type="email" className="inp" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</Field>
        <Field label="Perfil" className="col-span-2" hint={PERFIS[f.perfil]?.desc}>{(id) => (
          <select id={id} className="inp" value={f.perfil} onChange={(e) => setF({ ...f, perfil: e.target.value })}>
            {Object.entries(PERFIS).filter(([k]) => admin || k !== 'administrador' || u?.perfil === k).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>)}</Field>
        {!u && <Field label="Palavra-passe temporária" className="col-span-2" error={pe} hint="O utilizador pode alterá-la depois de entrar">
          {(id) => <input id={id} className={`inp ${pe ? 'inp-err' : ''}`} value={f.password} autoComplete="new-password" onChange={(e) => setF({ ...f, password: e.target.value })} />}</Field>}
        {u && <label className="col-span-2 flex items-center gap-2 text-[13.5px]"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={f.ativo} onChange={(e) => setF({ ...f, ativo: e.target.checked })} />Ativo</label>}
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function SenhaDialog({ u, onClose }: { u: U; onClose: () => void }) {
  const toast = useToast()
  const [p, setP] = useState('')
  const m = useMutation({
    mutationFn: () => api(`/utilizadores/${u.id}/password`, { method: 'POST', body: { password: p } }),
    onSuccess: () => { toast('Palavra-passe reposta. Comunique-a ao utilizador.'); onClose() },
  })
  const e = senhaErro(p)
  return (
    <Modal title={`Repor palavra-passe · ${u.nome}`} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!p || !!e} onClick={() => m.mutate()}>Repor</Button></>}>
      <Field label="Nova palavra-passe temporária" error={e}>{(id) => <input id={id} className={`inp ${e ? 'inp-err' : ''}`} value={p} autoComplete="new-password" onChange={(ev) => setP(ev.target.value)} />}</Field>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

export function MinhaSenhaDialog({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const [f, setF] = useState({ atual: '', nova: '', rep: '' })
  const e = senhaErro(f.nova) ?? (f.rep && f.rep !== f.nova ? 'As palavras-passe não coincidem' : null)
  const m = useMutation({
    mutationFn: () => api('/auth/password', { method: 'PUT', body: { atual: f.atual, nova: f.nova } }),
    onSuccess: () => { toast('Palavra-passe alterada'); onClose() },
  })
  return (
    <Modal title="Alterar a minha palavra-passe" onClose={onClose} width={440}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.atual || !f.nova || f.rep !== f.nova || !!e} onClick={() => m.mutate()}>Alterar</Button></>}>
      <div className="flex flex-col gap-3.5">
        <Field label="Palavra-passe atual">{(id) => <input id={id} type="password" autoComplete="current-password" className="inp" value={f.atual} onChange={(ev) => setF({ ...f, atual: ev.target.value })} />}</Field>
        <Field label="Nova palavra-passe">{(id) => <input id={id} type="password" autoComplete="new-password" className="inp" value={f.nova} onChange={(ev) => setF({ ...f, nova: ev.target.value })} />}</Field>
        <Field label="Repetir a nova palavra-passe" error={e}>{(id) => <input id={id} type="password" autoComplete="new-password" className="inp" value={f.rep} onChange={(ev) => setF({ ...f, rep: ev.target.value })} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
