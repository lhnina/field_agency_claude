import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AreaBadge, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { api } from '../lib/api'
import { ESTADO_CONTRATO, dataCurta, eur, horas, iso } from '../lib/format'
import type { Cliente, Contrato, ContratoResumo, TipoContrato } from '../lib/types'

export default function Contratos() {
  const nav = useNavigate()
  const [tipo, setTipo] = useState('')
  const [q, setQ] = useState('')
  const [novo, setNovo] = useState(false)
  const lista = useQuery({ queryKey: ['contratos', tipo], queryFn: () => api<ContratoResumo[]>('/contratos', { params: { tipo } }) })
  const itens = (lista.data ?? []).filter((c) => !q || `${c.numero} ${c.cliente_nome} ${c.marca_nome ?? ''}`.toLowerCase().includes(q.toLowerCase()))
  const ativos = (lista.data ?? []).filter((c) => c.estado === 'ativo')
  const total = ativos.reduce((s, c) => s + Number(c.valor_mensal), 0)

  return (
    <>
      <PageHeader crumb="Comercial" title="Contratos" sub={`${ativos.length} contratos ativos · ${eur(total, 0)} de faturação mensal prevista`}>
        <Button variant="primary" icon="plus" onClick={() => setNovo(true)}>Novo contrato</Button>
      </PageHeader>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-3">
          <Seg label="Área" value={tipo} onChange={setTipo} options={[{ value: '', label: 'Todos' }, { value: 'REP', label: 'Reposição' }, { value: 'PRO', label: 'Promoções' }, { value: 'LOG', label: 'Logística' }, { value: 'EQF', label: 'Equipas Fixas' }]} />
          <label className="flex items-center gap-2 h-[34px] w-[260px] px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
            <Icon name="search" size={16} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="N.º, cliente ou marca" aria-label="Pesquisar contratos" className="flex-1 min-w-0 bg-transparent outline-none text-[13.5px] text-ink" />
          </label>
          <span className="flex-1" />
          <span className="text-[12.5px] text-ink-60">{itens.length} contratos · ordenado por valor mensal</span>
        </div>
        {lista.isLoading ? <Loading /> : lista.error ? <div className="p-4"><ErrorBox error={lista.error} /></div> : itens.length === 0 ? <Empty title="Sem contratos">Crie o primeiro contrato para começar a planear.</Empty> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Contrato</th><th>Área</th><th>Estado</th><th>Vigência</th><th className="text-right">Lojas</th><th className="text-right">Horas/semana</th><th className="text-right">Contratadas/mês</th><th className="text-right">Valor mensal</th><th /></tr></thead>
              <tbody>
                {itens.map((c) => (
                  <tr key={c.id} className="cursor-pointer" onClick={() => nav(`/contratos/${c.id}`)}>
                    <td>
                      <a href={`/contratos/${c.id}`} onClick={(e) => { e.preventDefault(); nav(`/contratos/${c.id}`) }} className="font-mono text-[12.5px] font-medium text-petrol-600">{c.numero}</a>
                      <div className="font-medium">{c.cliente_nome}</div>
                      <div className="text-xs text-ink-60">{c.evento ?? c.descricao ?? c.marca_nome}</div>
                    </td>
                    <td><AreaBadge tipo={c.tipo} /></td>
                    <td><Badge tone={ESTADO_CONTRATO[c.estado].tone} dot>{ESTADO_CONTRATO[c.estado].label}</Badge></td>
                    <td className="text-[12.5px] text-ink-60 num">{dataCurta(c.inicio)} – {c.fim ? dataCurta(c.fim) : 'sem termo'}</td>
                    <td className="text-right num">{c.n_linhas}{c.linhas_por_atribuir > 0 && <div className="text-xs text-err-fg">{c.linhas_por_atribuir} por atribuir</div>}</td>
                    <td className="text-right num">{horas(c.horas_semana)}</td>
                    <td className="text-right num">{horas(c.horas_mes)}</td>
                    <td className="text-right num font-medium">{eur(c.valor_mensal)}</td>
                    <td className="text-right"><Icon name="cr" size={16} className="text-ink-60" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {novo && <NovoContrato onClose={() => setNovo(false)} onCriado={(c) => nav(`/contratos/${c.id}`)} />}
    </>
  )
}

export function NovoContrato({ onClose, onCriado, inicial }: { onClose: () => void; onCriado: (c: Contrato) => void; inicial?: Contrato }) {
  const qc = useQueryClient()
  const toast = useToast()
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<Cliente[]>('/clientes') })
  const hoje = iso(new Date())
  const [f, setF] = useState({
    tipo: (inicial?.tipo ?? 'REP') as TipoContrato, cliente_id: inicial ? String(inicial.cliente_id) : '', marca_id: inicial?.marca_id ? String(inicial.marca_id) : '',
    data: inicial?.data ?? hoje, inicio: inicial?.inicio ?? hoje, fim: inicial?.fim ?? '', descricao: inicial?.descricao ?? '', evento: inicial?.evento ?? '', observacoes: inicial?.observacoes ?? '',
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value })
  const cli = clientes.data?.find((c) => String(c.id) === f.cliente_id)
  const m = useMutation({
    mutationFn: () => api<Contrato>(inicial ? `/contratos/${inicial.id}` : '/contratos', {
      method: inicial ? 'PUT' : 'POST',
      body: { ...f, cliente_id: Number(f.cliente_id), marca_id: f.marca_id ? Number(f.marca_id) : null, fim: f.fim || null, descricao: f.descricao || null, evento: f.evento || null, observacoes: f.observacoes || null },
    }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['contratos'] }); qc.invalidateQueries({ queryKey: ['contrato', c.id] }); toast(inicial ? 'Contrato atualizado' : `Contrato ${c.numero} criado`); onCriado(c) },
  })
  const fimErr = f.fim && f.fim < f.inicio ? 'A data de fim é anterior à data de início' : null
  return (
    <Modal title={inicial ? `Editar ${inicial.numero}` : 'Novo contrato'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.cliente_id || !!fimErr} onClick={() => m.mutate()}>{inicial ? 'Guardar' : 'Criar contrato'}</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Tipo">{(id) => (
          <select id={id} className="inp" value={f.tipo} onChange={set('tipo')} disabled={!!inicial}>
            <option value="REP">Reposição</option><option value="PRO">Promoção / ativação</option>
            <option value="LOG" disabled>Logística (próximo incremento)</option><option value="EQF" disabled>Equipas Fixas (próximo incremento)</option>
          </select>)}</Field>
        <Field label="Data do contrato">{(id) => <input id={id} type="date" className="inp" value={f.data} onChange={set('data')} />}</Field>
        <Field label="Cliente">{(id) => (
          <select id={id} className="inp" value={f.cliente_id} onChange={(e) => setF({ ...f, cliente_id: e.target.value, marca_id: '' })}>
            <option value="">Escolher…</option>{clientes.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>)}</Field>
        <Field label="Marca">{(id) => (
          <select id={id} className="inp" value={f.marca_id} onChange={set('marca_id')} disabled={!cli}>
            <option value="">—</option>{cli?.marcas.map((mm) => <option key={mm.id} value={mm.id}>{mm.nome}</option>)}
          </select>)}</Field>
        <Field label="Início">{(id) => <input id={id} type="date" className="inp" value={f.inicio} onChange={set('inicio')} />}</Field>
        <Field label="Fim" hint="Vazio = sem termo" error={fimErr}>{(id) => <input id={id} type="date" className={`inp ${fimErr ? 'inp-err' : ''}`} value={f.fim} onChange={set('fim')} />}</Field>
        {f.tipo === 'PRO'
          ? <Field label="Evento / campanha" className="col-span-2">{(id) => <input id={id} className="inp" value={f.evento} onChange={set('evento')} placeholder="Ex.: Campanha de Natal" />}</Field>
          : <Field label="Descrição" className="col-span-2">{(id) => <input id={id} className="inp" value={f.descricao} onChange={set('descricao')} placeholder="Ex.: Reposição em lojas da Grande Lisboa" />}</Field>}
        <Field label="Observações" className="col-span-2">{(id) => <textarea id={id} className="inp h-20 py-2" value={f.observacoes} onChange={set('observacoes')} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
