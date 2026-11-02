import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { api } from '../lib/api'
import type { Cliente, IdNome, Loja } from '../lib/types'

export default function ClientesLojas() {
  const [tab, setTab] = useState<'clientes' | 'lojas'>('lojas')
  const [novo, setNovo] = useState(false)
  return (
    <>
      <PageHeader crumb="Comercial" title="Clientes e lojas">
        <Button variant="primary" icon="plus" onClick={() => setNovo(true)}>{tab === 'lojas' ? 'Nova loja' : 'Novo cliente'}</Button>
      </PageHeader>
      <Card className="overflow-hidden">
        <div role="tablist" className="flex gap-0.5 border-b border-line px-[18px]">
          {(['lojas', 'clientes'] as const).map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`h-10 px-3 text-[13.5px] -mb-px border-b-2 ${tab === t ? 'border-petrol-600 font-medium' : 'border-transparent text-ink-60 hover:text-ink'}`}>
              {t === 'lojas' ? 'Lojas' : 'Clientes e marcas'}
            </button>
          ))}
        </div>
        {tab === 'lojas' ? <Lojas /> : <Clientes />}
      </Card>
      {novo && (tab === 'lojas' ? <LojaDialog onClose={() => setNovo(false)} /> : <ClienteDialog onClose={() => setNovo(false)} />)}
    </>
  )
}

function Lojas() {
  const [q, setQ] = useState('')
  const lojas = useQuery({ queryKey: ['lojas', q], queryFn: () => api<Loja[]>('/lojas', { params: { q } }) })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const [edit, setEdit] = useState<Loja | null>(null)
  return (
    <>
      <div className="px-3.5 py-3">
        <label className="flex items-center gap-2 h-[34px] w-[280px] px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
          <Icon name="search" size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome da loja" aria-label="Pesquisar lojas" className="flex-1 bg-transparent outline-none text-[13.5px] text-ink" />
        </label>
      </div>
      {lojas.isLoading ? <Loading /> : lojas.error ? <div className="p-4"><ErrorBox error={lojas.error} /></div> : !lojas.data?.length ? <Empty title="Sem lojas" /> : (
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Loja</th><th>Insígnia</th><th>Zona</th><th>Nome na credencial</th><th>Horário</th><th>Supervisor</th><th /></tr></thead>
            <tbody>{lojas.data.map((l) => (
              <tr key={l.id}>
                <td className="font-medium">{l.nome}<div className="text-xs text-ink-60 font-normal">{[l.morada, l.localidade].filter(Boolean).join(', ')}</div></td>
                <td>{l.insignia?.nome ?? '—'}</td><td>{l.zona?.nome ?? '—'}</td>
                <td className="text-[12.5px] font-mono">{l.nome_credencial ?? '—'}</td>
                <td className="text-[12.5px] text-ink-60">{l.horario_semana ?? '—'}{l.horario_fim_semana ? ` · fds ${l.horario_fim_semana}` : ''}</td>
                <td className="text-[12.5px]">{sups.data?.find((s) => s.id === l.supervisor_id)?.nome ?? '—'}</td>
                <td className="text-right"><button type="button" aria-label={`Editar ${l.nome}`} onClick={() => setEdit(l)} className="p-1 text-ink-60 hover:text-ink"><Icon name="edit" size={16} /></button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {edit && <LojaDialog loja={edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function Clientes() {
  const cl = useQuery({ queryKey: ['clientes'], queryFn: () => api<Cliente[]>('/clientes') })
  if (cl.isLoading) return <Loading />
  if (cl.error) return <div className="p-4"><ErrorBox error={cl.error} /></div>
  if (!cl.data?.length) return <Empty title="Sem clientes" />
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead><tr><th>Cliente</th><th>NIF</th><th>Código PHC</th><th>Marcas</th></tr></thead>
        <tbody>{cl.data.map((c) => (
          <tr key={c.id}><td className="font-medium">{c.nome}</td><td className="num">{c.nif ?? '—'}</td><td className="num font-mono text-[12.5px]">{c.codigo_phc ?? '—'}</td>
            <td><div className="flex flex-wrap gap-1">{c.marcas.map((m) => <Badge key={m.id}>{m.nome}</Badge>)}</div></td></tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function LojaDialog({ loja, onClose }: { loja?: Loja; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const ins = useQuery({ queryKey: ['insignias'], queryFn: () => api<IdNome[]>('/insignias') })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const campos = ['nome', 'nome_credencial', 'morada', 'codigo_postal', 'localidade', 'horario_semana', 'horario_fim_semana', 'contacto_nome', 'contacto_funcao', 'contacto_email', 'contacto_telefone'] as const
  const [f, setF] = useState<Record<string, string>>(() => {
    const o: Record<string, string> = { insignia_id: String(loja?.insignia_id ?? ''), zona_id: String(loja?.zona_id ?? ''), supervisor_id: String(loja?.supervisor_id ?? '') }
    campos.forEach((k) => { o[k] = (loja?.[k] as string | null) ?? '' })
    return o
  })
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })
  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {}
      campos.forEach((k) => { body[k] = f[k] || null })
      body.nome = f.nome
      ;(['insignia_id', 'zona_id', 'supervisor_id'] as const).forEach((k) => { body[k] = f[k] ? Number(f[k]) : null })
      return api(loja ? `/lojas/${loja.id}` : '/lojas', { method: loja ? 'PUT' : 'POST', body })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['lojas'] }); toast(loja ? 'Loja atualizada' : 'Loja criada'); onClose() },
  })
  const txt = (k: string, label: string, cls = '') => <Field label={label} className={cls}>{(id) => <input id={id} className="inp" value={f[k]} onChange={set(k)} />}</Field>
  const sel = (k: string, label: string, opts?: IdNome[]) => <Field label={label}>{(id) => <select id={id} className="inp" value={f[k]} onChange={set(k)}><option value="">—</option>{opts?.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}</select>}</Field>
  return (
    <Modal title={loja ? `Editar ${loja.nome}` : 'Nova loja'} onClose={onClose} width={640}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-3 gap-3.5">
        {txt('nome', 'Nome do ponto de venda', 'col-span-2')}{sel('insignia_id', 'Insígnia', ins.data)}
        {txt('nome_credencial', 'Nome para credencial', 'col-span-2')}{sel('zona_id', 'Zona', zonas.data)}
        {txt('morada', 'Morada', 'col-span-3')}
        {txt('codigo_postal', 'Código postal')}{txt('localidade', 'Localidade')}{sel('supervisor_id', 'Supervisor da agência', sups.data)}
        {txt('horario_semana', 'Horário (semana)')}{txt('horario_fim_semana', 'Horário (fim de semana)')}<span />
        {txt('contacto_nome', 'Contacto na loja')}{txt('contacto_funcao', 'Função')}{txt('contacto_telefone', 'Telefone')}
        {txt('contacto_email', 'Email do contacto', 'col-span-3')}
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function ClienteDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [f, setF] = useState({ nome: '', nif: '', codigo_phc: '', marcas: '' })
  const m = useMutation({
    mutationFn: () => api('/clientes', { method: 'POST', body: { nome: f.nome, nif: f.nif || null, codigo_phc: f.codigo_phc ? Number(f.codigo_phc) : null, marcas: f.marcas.split(',').map((s) => s.trim()).filter(Boolean) } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['clientes'] }); toast('Cliente criado'); onClose() },
  })
  return (
    <Modal title="Novo cliente" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Nome" className="col-span-2">{(id) => <input id={id} className="inp" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Field>
        <Field label="NIF">{(id) => <input id={id} className="inp" value={f.nif} onChange={(e) => setF({ ...f, nif: e.target.value })} />}</Field>
        <Field label="Código de cliente no PHC">{(id) => <input id={id} inputMode="numeric" className="inp" value={f.codigo_phc} onChange={(e) => setF({ ...f, codigo_phc: e.target.value })} />}</Field>
        <Field label="Marcas" hint="Separadas por vírgulas" className="col-span-2">{(id) => <input id={id} className="inp" value={f.marcas} onChange={(e) => setF({ ...f, marcas: e.target.value })} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
