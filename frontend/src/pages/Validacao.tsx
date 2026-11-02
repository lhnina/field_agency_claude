import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AreaBadge, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { api } from '../lib/api'
import { addDays, diaMes, diaSemana, horas, iso, num } from '../lib/format'
import type { TipoContrato } from '../lib/types'

type Item = {
  id: number; data: string; colaborador_id: number; colaborador: string; loja: string; cliente: string; tipo: TipoContrato
  contrato_numero: string; horas_planeadas: number; horas_executadas: number | null; horas_aprovadas: number | null
  diferenca: number | null; origem: 'tacita' | 'manual' | 'registo' | null; estado: string; observacao: string | null
  substituicao: boolean; bloqueado: string | null
}
type Lista = { inicio: string; fim: string; itens: Item[]; resumo: { total: number; tacitas: number; com_diferenca: number; horas_planeadas: number; horas_executadas: number } }

const ORIGEM: Record<string, { label: string; tone: 'neu' | 'info' | 'warn' }> = {
  tacita: { label: 'Tácita', tone: 'neu' }, manual: { label: 'Corrigida', tone: 'warn' }, registo: { label: 'Registo', tone: 'info' },
}

export default function Validacao() {
  const qc = useQueryClient()
  const toast = useToast()
  const hoje = new Date()
  const [estado, setEstado] = useState('por_validar')
  const [inicio, setInicio] = useState(iso(new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1)))
  const [fim, setFim] = useState(iso(addDays(hoje, -1)))
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [soDif, setSoDif] = useState(false)
  const [editar, setEditar] = useState<Item | null>(null)
  const [rejeitar, setRejeitar] = useState(false)

  const params = { estado, inicio, fim }
  const q = useQuery({ queryKey: ['validacao', params], queryFn: () => api<Lista>('/validacao', { params }) })
  const itens = useMemo(() => (q.data?.itens ?? []).filter((i) => !soDif || i.diferenca), [q.data, soDif])
  const editaveis = itens.filter((i) => !i.bloqueado)
  const refresh = () => { setSel(new Set()); qc.invalidateQueries({ queryKey: ['validacao'] }); qc.invalidateQueries({ queryKey: ['apuramento'] }); qc.invalidateQueries({ queryKey: ['prefaturacao'] }) }
  const validar = useMutation({
    mutationFn: (v: { ids: number[]; aprovar: boolean; motivo?: string }) => api<{ processadas: number; erros: { id: number; erro: string }[] }>('/validacao', { method: 'POST', body: v }),
    onSuccess: (r, v) => {
      refresh()
      toast(`${r.processadas} ${v.aprovar ? 'validados' : 'rejeitados'}${r.erros.length ? ` · ${r.erros.length} ignorados` : ''}`, r.erros.length ? 'warn' : 'ok')
    },
    onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })

  const todos = editaveis.length > 0 && editaveis.every((i) => sel.has(i.id))
  const toggle = (id: number) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  return (
    <>
      <PageHeader crumb="Operação" title="Validação de horas"
        sub="Sem registo do colaborador, o serviço conta com as horas planeadas (aceitação tácita), também para remuneração.">
        <Seg label="Estado" value={estado} onChange={(v) => { setEstado(v); setSel(new Set()) }}
          options={[{ value: 'por_validar', label: 'Por validar' }, { value: 'validadas', label: 'Validadas' }, { value: 'rejeitadas', label: 'Rejeitadas' }]} />
      </PageHeader>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="De">{(id) => <input id={id} type="date" className="inp w-[160px]" value={inicio} onChange={(e) => setInicio(e.target.value)} />}</Field>
        <Field label="Até">{(id) => <input id={id} type="date" className="inp w-[160px]" value={fim} max={iso(hoje)} onChange={(e) => setFim(e.target.value)} />}</Field>
        <label className="flex items-center gap-2 h-9 text-[13px]"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={soDif} onChange={(e) => setSoDif(e.target.checked)} />Só com diferença face ao planeado</label>
        <span className="flex-1" />
        {q.data && <>
          <Badge>{q.data.resumo.total} serviços</Badge>
          <Badge tone="neu">{q.data.resumo.tacitas} tácitos</Badge>
          <Badge tone={q.data.resumo.com_diferenca ? 'warn' : 'neu'} dot>{q.data.resumo.com_diferenca} com diferença</Badge>
          <Badge className="num">{horas(q.data.resumo.horas_executadas)} de {horas(q.data.resumo.horas_planeadas)}</Badge>
        </>}
      </div>

      <Card className="overflow-hidden">
        {estado === 'por_validar' && (
          <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 bg-[#FAFBF9] border-b border-line-soft">
            <span className="text-[13px] text-ink-60">{sel.size ? `${sel.size} selecionados` : 'Selecione os serviços a validar'}</span>
            <span className="flex-1" />
            <Button size="sm" variant="danger" disabled={!sel.size} onClick={() => setRejeitar(true)}>Rejeitar</Button>
            <Button size="sm" variant="primary" icon="check" disabled={!sel.size} loading={validar.isPending}
              onClick={() => validar.mutate({ ids: [...sel], aprovar: true })}>Validar selecionados</Button>
          </div>
        )}
        {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : itens.length === 0 ? (
          <Empty title={estado === 'por_validar' ? 'Nada por validar neste período' : 'Sem registos'} />
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr>
                {estado === 'por_validar' && <th className="w-8"><input type="checkbox" aria-label="Selecionar todos" className="w-4 h-4 accent-petrol-600" checked={todos}
                  onChange={() => setSel(todos ? new Set() : new Set(editaveis.map((i) => i.id)))} /></th>}
                <th>Dia</th><th>Colaborador</th><th>Loja · cliente</th><th>Área</th>
                <th className="text-right">Planeadas</th><th className="text-right">Executadas</th><th className="text-right">Diferença</th><th>Origem</th><th>Observação</th><th />
              </tr></thead>
              <tbody>
                {itens.map((i) => (
                  <tr key={i.id} className={sel.has(i.id) ? '[&>td]:!bg-[#EAF4F2]' : ''}>
                    {estado === 'por_validar' && <td><input type="checkbox" aria-label={`Selecionar ${i.colaborador} ${i.data}`} className="w-4 h-4 accent-petrol-600"
                      disabled={!!i.bloqueado} checked={sel.has(i.id)} onChange={() => toggle(i.id)} /></td>}
                    <td className="num whitespace-nowrap">{diaSemana(i.data)} {diaMes(i.data)}</td>
                    <td className="font-medium">{i.colaborador}{i.substituicao && <span className="block text-xs text-ink-60 font-normal">substituição</span>}</td>
                    <td>{i.loja}<div className="text-xs text-ink-60">{i.cliente}</div></td>
                    <td><AreaBadge tipo={i.tipo} /></td>
                    <td className="text-right num">{num(i.horas_planeadas)}</td>
                    <td className="text-right num font-medium">{i.horas_executadas === null ? '—' : num(i.horas_executadas)}</td>
                    <td className={`text-right num ${i.diferenca ? (i.diferenca > 0 ? 'text-warn-fg font-medium' : 'text-err-fg font-medium') : 'text-ink-40'}`}>
                      {i.diferenca ? `${i.diferenca > 0 ? '+' : ''}${num(i.diferenca)}` : '–'}</td>
                    <td>{i.origem ? <Badge tone={ORIGEM[i.origem].tone}>{ORIGEM[i.origem].label}</Badge> : <Badge tone="err">Sem registo</Badge>}</td>
                    <td className="text-xs text-ink-60 max-w-[220px]">{i.bloqueado ? <span className="text-warn-fg">{i.bloqueado}</span> : i.observacao}</td>
                    <td className="text-right">{!i.bloqueado && estado !== 'rejeitadas' &&
                      <button type="button" aria-label="Corrigir horas" onClick={() => setEditar(i)} className="p-1 text-ink-60 hover:text-ink"><Icon name="edit" size={16} /></button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {editar && <CorrigirDialog item={editar} onClose={() => setEditar(null)} onDone={() => { setEditar(null); refresh() }} />}
      {rejeitar && <RejeitarDialog n={sel.size} onClose={() => setRejeitar(false)}
        onConfirm={(motivo) => { validar.mutate({ ids: [...sel], aprovar: false, motivo }); setRejeitar(false) }} />}
    </>
  )
}

function CorrigirDialog({ item, onClose, onDone }: { item: Item; onClose: () => void; onDone: () => void }) {
  const toast = useToast()
  const [h, setH] = useState(String(item.horas_executadas ?? item.horas_planeadas).replace('.', ','))
  const [obs, setObs] = useState(item.observacao ?? '')
  const valor = Number(h.replace(',', '.'))
  const invalido = Number.isNaN(valor) || valor < 0 || valor > 24
  const precisaMotivo = item.estado === 'validado' || valor !== item.horas_planeadas
  const m = useMutation({
    mutationFn: () => api(`/ocorrencias/${item.id}/execucao`, { method: 'PUT', body: { horas: valor, observacao: obs || null } }),
    onSuccess: () => { toast(item.estado === 'validado' ? 'Horas corrigidas; o serviço volta a ficar por validar' : 'Horas registadas'); onDone() },
  })
  return (
    <Modal title={`Horas de ${item.colaborador} · ${diaSemana(item.data)} ${diaMes(item.data)}`} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="primary" loading={m.isPending} disabled={invalido || (precisaMotivo && !obs.trim())} onClick={() => m.mutate()}>Guardar</Button></>}>
      <p className="text-[13px] text-ink-60 mb-3">{item.loja} · {item.cliente} · planeadas {horas(item.horas_planeadas)}</p>
      <div className="grid grid-cols-[140px_1fr] gap-3.5">
        <Field label="Horas executadas" error={invalido ? 'Entre 0 e 24' : null}>{(id) => <input id={id} inputMode="decimal" className={`inp num ${invalido ? 'inp-err' : ''}`} value={h} onChange={(e) => setH(e.target.value)} />}</Field>
        <Field label="Motivo" hint={precisaMotivo ? 'Obrigatório quando difere do planeado' : undefined}>{(id) => <input id={id} className="inp" value={obs} onChange={(e) => setObs(e.target.value)} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function RejeitarDialog({ n, onClose, onConfirm }: { n: number; onClose: () => void; onConfirm: (m: string) => void }) {
  const [motivo, setMotivo] = useState('')
  return (
    <Modal title={`Rejeitar ${n} ${n === 1 ? 'serviço' : 'serviços'}`} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" className="!bg-err !border-err" disabled={!motivo.trim()} onClick={() => onConfirm(motivo)}>Rejeitar</Button></>}>
      <p className="text-[13px] mb-3">Um serviço rejeitado conta com 0 horas para custo e remuneração. A faturação de Reposição não muda, porque é feita pelas horas contratadas.</p>
      <Field label="Motivo">{(id) => <input id={id} className="inp" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: loja fechada, colaborador faltou" autoFocus />}</Field>
    </Modal>
  )
}
