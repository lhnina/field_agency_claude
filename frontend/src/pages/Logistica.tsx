import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AcaoIcone, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { LojaPicker } from '../components/LojaPicker'
import { InsigniaLogo } from '../components/InsigniaLogo'
import { MostrarInativos } from '../components/Estado'
import { abrirFicheiro, api, apiForm, session } from '../lib/api'
import { addDays, dataCurta, diaMes, diaSemana, eur, iso, intervaloSemana, num, segunda } from '../lib/format'
import type { Cliente, Contrato, EstadoServicoLog, ServicoLog, TipoServicoLog, Viatura } from '../lib/types'

export const TIPOS_LOG: { v: TipoServicoLog; l: string }[] = [
  { v: 'entrega', l: 'Entrega' }, { v: 'recolha', l: 'Recolha' }, { v: 'implementacao', l: 'Implementação' },
  { v: 'entrega_implementacao', l: 'Entrega + Implementação' }, { v: 'desmontagem', l: 'Desmontagem' },
]
export const ESTADO_LOG: Record<EstadoServicoLog, { label: string; tone: 'neu' | 'info' | 'warn' | 'ok' | 'err' }> = {
  planeado: { label: 'Por atribuir', tone: 'err' }, atribuido: { label: 'Atribuído', tone: 'info' },
  executado: { label: 'Por validar', tone: 'warn' }, validado: { label: 'Validado', tone: 'ok' }, cancelado: { label: 'Cancelado', tone: 'neu' },
}
const perfil = () => session.user()?.perfil ?? ''
const podePlanear = () => ['administrador', 'gestor', 'gestor_conta', 'supervisor'].includes(perfil())
const podeContratos = () => ['administrador', 'gestor', 'gestor_conta'].includes(perfil())
const podeViaturas = () => ['administrador', 'gestor', 'gestor_conta'].includes(perfil())
const invalidar = (qc: ReturnType<typeof useQueryClient>) => ['logistica', 'contrato-servicos', 'contratos', 'contrato', 'prefaturacao', 'dashboard-logistica']
  .forEach((k) => qc.invalidateQueries({ queryKey: [k] }))

type Lista = { itens: ServicoLog[]; resumo: { total: number; por_atribuir: number; por_executar: number; por_validar: number; com_alertas: number; valor: number; custo: number; km: number } }

export default function Logistica() {
  const [tab, setTab] = useState('servicos')
  return (
    <>
      <PageHeader crumb="Operação" title="Logística" sub="Entregas, recolhas e implementações: viatura, motorista, km, portagens e comprovativos.">
        <Seg label="Secção" value={tab} onChange={setTab} options={[{ value: 'servicos', label: 'Serviços' }, { value: 'viaturas', label: 'Viaturas' }]} />
      </PageHeader>
      {tab === 'servicos' ? <Servicos /> : <Viaturas />}
    </>
  )
}

// ------------------------------------------------------------------ serviços da semana
function Servicos() {
  const qc = useQueryClient()
  const toast = useToast()
  const [inicio, setInicio] = useState(() => iso(segunda(new Date())))
  const fim = iso(addDays(new Date(inicio), 6))
  const [estado, setEstado] = useState('')
  const [viatura, setViatura] = useState('')
  const [cliente, setCliente] = useState('')
  const [atribuir, setAtribuir] = useState<ServicoLog | null>(null)
  const [executar, setExecutar] = useState<ServicoLog | null>(null)
  const [editar, setEditar] = useState<ServicoLog | null>(null)
  const [cancelar, setCancelar] = useState<ServicoLog | null>(null)
  const [detalhe, setDetalhe] = useState<ServicoLog | null>(null)
  const params = { inicio, fim, estado, viatura_id: viatura, cliente_id: cliente }
  const q = useQuery({ queryKey: ['logistica', params], queryFn: () => api<Lista>('/logistica/servicos', { params }) })
  const viaturas = useQuery({ queryKey: ['viaturas'], queryFn: () => api<Viatura[]>('/viaturas') })
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<Cliente[]>('/clientes') })
  const validar = useMutation({
    mutationFn: (ids: number[]) => api<{ processados: number }>('/servicos-logisticos/validar', { method: 'POST', body: { ids, aprovar: true } }),
    onSuccess: (r) => { invalidar(qc); toast(`${r.processados} serviço(s) validado(s)`) },
    onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })
  const porDia = useMemo(() => {
    const m = new Map<string, ServicoLog[]>()
    for (let i = 0; i < 7; i++) m.set(iso(addDays(new Date(inicio), i)), [])
    for (const s of q.data?.itens ?? []) m.get(s.data)?.push(s)
    return [...m.entries()]
  }, [q.data, inicio])
  const hoje = iso(new Date())
  const r = q.data?.resumo
  const porValidar = (q.data?.itens ?? []).filter((s) => s.estado === 'executado')
  const sel = (label: string, value: string, set: (v: string) => void, ops: { v: string | number; l: string }[], todos = 'Todos') => (
    <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">{label}
      <select aria-label={label} className="outline-none font-medium text-ink bg-transparent max-w-[220px]" value={value} onChange={(e) => set(e.target.value)}>
        <option value="">{todos}</option>{ops.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select></label>
  )
  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
          <div className="flex items-center gap-1">
            <AcaoIcone icon="cl" label="Semana anterior" onClick={() => setInicio(iso(addDays(new Date(inicio), -7)))} />
            <Button size="sm" variant="secondary" onClick={() => setInicio(iso(segunda(new Date())))}>Esta semana</Button>
            <AcaoIcone icon="cr" label="Semana seguinte" onClick={() => setInicio(iso(addDays(new Date(inicio), 7)))} />
          </div>
          <span className="text-[13.5px] font-semibold ml-1">{intervaloSemana(inicio, fim)}</span>
          <span className="flex-1" />
          {sel('Mostrar', estado, setEstado, [{ v: 'pendentes', l: 'Por executar' }, { v: 'planeado', l: 'Por atribuir' }, { v: 'executado', l: 'Por validar' }, { v: 'validado', l: 'Validados' }, { v: 'cancelado', l: 'Cancelados' }])}
          {sel('Viatura', viatura, setViatura, (viaturas.data ?? []).map((v) => ({ v: v.id, l: v.matricula })), 'Todas')}
          {sel('Cliente', cliente, setCliente, (clientes.data ?? []).map((c) => ({ v: c.id, l: c.nome })))}
        </div>
        {r && (
          <div className="grid grid-cols-2 md:grid-cols-6 border-b border-line-soft">
            {[
              ['Serviços', String(r.total), 'na semana', ''],
              ['Por atribuir', String(r.por_atribuir), 'sem viatura ou motorista', r.por_atribuir ? 'text-err-fg' : ''],
              ['Por executar', String(r.por_executar), 'sem registo', ''],
              ['Por validar', String(r.por_validar), 'registados', r.por_validar ? 'text-warn-fg' : ''],
              ['Valor', eur(r.valor), 'dos serviços da semana', ''],
              ['Custo registado', eur(r.custo), `${num(r.km, 0)} km`, ''],
            ].map(([l, v, s, cls], i) => (
              <div key={l} className={`px-[18px] py-3 ${i < 5 ? 'md:border-r border-line-soft' : ''}`}>
                <div className="text-xs text-ink-60">{l}</div>
                <div className={`text-lg font-semibold num ${cls}`}>{v}</div>
                <div className="text-xs text-ink-60">{s}</div>
              </div>
            ))}
          </div>
        )}
        {porValidar.length > 0 && podePlanear() && (
          <div className="flex items-center gap-2 px-3.5 py-2.5 bg-warn-bg text-warn-fg text-[13px] border-b border-line-soft">
            <Icon name="alert" size={16} />{porValidar.length} serviço(s) com execução registada à espera de validação.
            <span className="flex-1" />
            <Button size="sm" variant="subtil" icon="check" loading={validar.isPending} onClick={() => validar.mutate(porValidar.map((s) => s.id))}>Validar todos</Button>
          </div>
        )}
        {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : (
          <div>
            {porDia.map(([dia, lista]) => (
              <div key={dia} className="border-b border-line-soft last:border-b-0">
                <div className={`flex items-center gap-2 px-[18px] py-2 text-[12.5px] ${dia === hoje ? 'bg-petrol-50 text-petrol-700 font-semibold' : 'bg-[#FAFBF9] text-ink-60'}`}>
                  <span className="capitalize">{diaSemana(dia)}, {diaMes(dia)}</span>{dia === hoje && <span>· hoje</span>}
                  <span className="flex-1" /><span>{lista.length ? `${lista.length} serviço${lista.length > 1 ? 's' : ''}` : '—'}</span>
                </div>
                {lista.map((s) => (
                  <LinhaServico key={s.id} s={s} hoje={hoje} onDetalhe={() => setDetalhe(s)} onAtribuir={() => setAtribuir(s)}
                    onExecutar={() => setExecutar(s)} onEditar={() => setEditar(s)} onCancelar={() => setCancelar(s)}
                    onValidar={() => validar.mutate([s.id])} />
                ))}
              </div>
            ))}
          </div>
        )}
      </Card>
      <p className="text-[12.5px] text-ink-60 flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />
        Os serviços criam-se nos contratos de Logística (ou por importação dos pedidos do ERP). Faturam-se pelo preço de cada serviço, depois de executados; o custo soma km × custo/km da viatura, portagens, outros custos e as horas do motorista e do ajudante.</p>
      {atribuir && <AtribuirDialog s={atribuir} onClose={() => setAtribuir(null)} />}
      {executar && <ExecucaoDialog s={executar} onClose={() => setExecutar(null)} />}
      {editar && <ServicoDialog contratoId={editar.contrato_id} s={editar} onClose={() => setEditar(null)} />}
      {cancelar && <CancelarDialog s={cancelar} onClose={() => setCancelar(null)} />}
      {detalhe && <DetalheDialog s={detalhe} onClose={() => setDetalhe(null)} />}
    </>
  )
}

export function LinhaServico({ s, hoje, onDetalhe, onAtribuir, onExecutar, onEditar, onCancelar, onValidar, mostrarData }: {
  s: ServicoLog; hoje: string; onDetalhe: () => void; onAtribuir: () => void; onExecutar: () => void; onEditar: () => void
  onCancelar: () => void; onValidar: () => void; mostrarData?: boolean
}) {
  const e = ESTADO_LOG[s.estado]
  const aberto = s.estado === 'planeado' || s.estado === 'atribuido'
  const cancelado = s.estado === 'cancelado'
  return (
    <div className={`grid grid-cols-[90px_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_110px_auto] items-center gap-3 px-[18px] py-2.5 border-t border-line-soft first:border-t-0 text-[13px] ${cancelado ? 'opacity-55' : ''}`}>
      <div className="num">
        {mostrarData && <div className="font-medium">{dataCurta(s.data)}</div>}
        <div className={mostrarData ? 'text-xs text-ink-60' : 'font-medium'}>{s.hora_inicio ? `${s.hora_inicio}–${s.hora_fim ?? ''}` : 'Sem hora'}</div>
        <div className="text-[11.5px] text-ink-60 truncate">{s.tipo_label}</div>
      </div>
      <button type="button" onClick={onDetalhe} className="flex items-center gap-2.5 min-w-0 text-left group">
        <InsigniaLogo id={s.insignia_id} v={s.insignia_logo_v} nome={s.insignia} size={28} inicial />
        <span className="min-w-0">
          <span className="block font-medium truncate group-hover:underline">{s.loja}</span>
          <span className="block text-xs text-ink-60 truncate">{s.materiais || s.loja_morada || '—'}</span>
        </span>
      </button>
      <div className="min-w-0">
        <div className="truncate">{s.cliente}</div>
        <div className="text-xs text-ink-60 truncate"><Link to={`/contratos/${s.contrato_id}`} className="font-mono text-petrol-600 hover:underline">{s.contrato_numero}</Link>{s.referencia_erp ? ` · ERP ${s.referencia_erp}` : ''}</div>
      </div>
      <button type="button" disabled={!aberto || !podePlanear()} onClick={onAtribuir}
        className={`min-w-0 text-left rounded-md px-2 py-1 -mx-2 ${aberto && podePlanear() ? 'hover:bg-petrol-50' : ''}`}>
        {s.viatura || s.colaborador ? <>
          <span className="flex items-center gap-1.5 truncate"><Icon name="truck" size={14} className="flex-none text-ink-60" />{s.viatura?.split(' · ')[0] ?? <span className="text-err-fg">sem viatura</span>}</span>
          <span className="block text-xs text-ink-60 truncate">{s.colaborador ?? <span className="text-err-fg">sem motorista</span>}{s.ajudante ? ` + ${s.ajudante}` : ''}</span>
        </> : <span className="inline-flex items-center gap-1.5 text-err-fg font-medium"><Icon name="plus" size={14} />Atribuir</span>}
      </button>
      <div>
        <Badge tone={e.tone} dot>{e.label}</Badge>
        {s.custos && <div className="text-xs text-ink-60 num mt-0.5" title={`Custo ${eur(s.custos.total)}`}>{eur(s.preco, 0)} · margem {eur(s.margem ?? 0, 0)}</div>}
        {s.alertas.length > 0 && <div className="text-xs text-warn-fg mt-0.5 flex items-center gap-1" title={s.alertas.join('\n')}><Icon name="alert" size={12} />{s.alertas.length} alerta{s.alertas.length > 1 ? 's' : ''}</div>}
      </div>
      <div className="flex items-center justify-end whitespace-nowrap">
        {aberto && podePlanear() && <AcaoIcone icon="truck" label="Atribuir viatura e motorista" onClick={onAtribuir} />}
        {aberto && s.data <= hoje && s.viatura_id && s.colaborador_id && podePlanear() && <AcaoIcone icon="check" label="Registar execução" onClick={onExecutar} className="!text-petrol-600 bg-petrol-50 hover:!bg-petrol-100" />}
        {s.estado === 'executado' && podePlanear() && <>
          <AcaoIcone icon="edit" label="Corrigir o registo de execução" onClick={onExecutar} />
          <AcaoIcone icon="check" label="Validar" onClick={onValidar} className="!text-ok-fg bg-ok-bg hover:!bg-[#CFEAD9]" />
        </>}
        {s.comprovativo_nome && <AcaoIcone icon="file" label={`Ver comprovativo (${s.comprovativo_nome})`} onClick={() => abrirFicheiro(`/servicos-logisticos/${s.id}/comprovativo`)} />}
        {aberto && podeContratos() && <AcaoIcone icon="edit" label="Editar serviço" onClick={onEditar} />}
        {(aberto || s.estado === 'executado') && podeContratos() && <AcaoIcone icon="trash" tom="perigo" label="Cancelar serviço" onClick={onCancelar} />}
      </div>
    </div>
  )
}

function DetalheDialog({ s, onClose }: { s: ServicoLog; onClose: () => void }) {
  const linha = (k: string, v: React.ReactNode) => v ? <div className="flex gap-3 py-1"><dt className="w-[150px] flex-none text-ink-60">{k}</dt><dd className="min-w-0">{v}</dd></div> : null
  return (
    <Modal title={`${s.tipo_label} · ${s.loja}`} onClose={onClose} width={620} footer={<Button variant="primary" onClick={onClose}>Fechar</Button>}>
      <dl className="text-[13px]">
        {linha('Data', `${dataCurta(s.data)}${s.hora_inicio ? `, ${s.hora_inicio}–${s.hora_fim ?? ''}` : ''}`)}
        {linha('Estado', <Badge tone={ESTADO_LOG[s.estado].tone} dot>{ESTADO_LOG[s.estado].label}</Badge>)}
        {linha('Cliente', `${s.cliente}${s.marca ? ` · ${s.marca}` : ''} · ${s.contrato_numero}`)}
        {linha('Referência ERP', s.referencia_erp)}
        {linha('Origem', s.origem)}
        {linha('Destino', [s.loja, s.loja_morada].filter(Boolean).join(' · '))}
        {linha('Materiais', <span className="whitespace-pre-line">{s.materiais}</span>)}
        {linha('Viatura', s.viatura)}
        {linha('Motorista', s.colaborador)}
        {linha('Ajudante', s.ajudante)}
        {linha('Preço', eur(s.preco))}
        {linha('Observações', <span className="whitespace-pre-line">{s.observacoes}</span>)}
        {s.custos && <>
          <div className="border-t border-line-soft my-2" />
          {linha('Km', `${s.km_partida ?? '—'} → ${s.km_chegada ?? '—'} (${s.custos.km} km · ${eur(s.custos.custo_km)})`)}
          {linha('Horas', `${s.inicio_real ?? '—'}–${s.fim_real ?? '—'} (${num(s.custos.horas)} h · ${eur(s.custos.mao_obra)})`)}
          {linha('Portagens', eur(s.custos.portagens))}
          {s.custos.outros > 0 && linha('Outros custos', `${eur(s.custos.outros)}${s.outros_custos_desc ? ` · ${s.outros_custos_desc}` : ''}`)}
          {linha('Custo total', <b>{eur(s.custos.total)}</b>)}
          {linha('Margem', <b className={(s.margem ?? 0) < 0 ? 'text-err-fg' : ''}>{eur(s.margem ?? 0)}</b>)}
          {linha('Observação', s.observacao_execucao)}
        </>}
        {linha('Motivo', s.motivo)}
        {s.alertas.length > 0 && linha('Alertas', <ul className="list-disc pl-4 text-warn-fg">{s.alertas.map((a) => <li key={a}>{a}</li>)}</ul>)}
      </dl>
    </Modal>
  )
}

// ------------------------------------------------------------------ diálogos
type Cand = { viaturas: { id: number; matricula: string; descricao: string | null; servicos_dia: number; conflito: boolean }[]
  colaboradores: { id: number; nome: string; funcao: string | null; zona: string | null; servicos_dia: number; alertas: string[] }[] }

function AtribuirDialog({ s, onClose }: { s: ServicoLog; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const c = useQuery({ queryKey: ['logistica-candidatos', s.id], queryFn: () => api<Cand>(`/servicos-logisticos/${s.id}/candidatos`) })
  const [f, setF] = useState({ viatura: s.viatura_id ? String(s.viatura_id) : '', motorista: s.colaborador_id ? String(s.colaborador_id) : '', ajudante: s.ajudante_id ? String(s.ajudante_id) : '' })
  const m = useMutation({
    mutationFn: () => api<ServicoLog>(`/servicos-logisticos/${s.id}/atribuicao`, { method: 'PUT', body: {
      viatura_id: f.viatura ? Number(f.viatura) : null, colaborador_id: f.motorista ? Number(f.motorista) : null, ajudante_id: f.ajudante ? Number(f.ajudante) : null } }),
    onSuccess: (r) => {
      invalidar(qc)
      toast(r.estado === 'atribuido' ? 'Serviço atribuído' : 'Atribuição guardada (falta viatura ou motorista)')
      if (r.alertas.length) toast(r.alertas.join(' · '), 'warn')
      onClose()
    },
  })
  const colab = (k: 'motorista' | 'ajudante', label: string, vazio: string) => (
    <Field label={label}>{(id) => (
      <select id={id} className="inp" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}>
        <option value="">{vazio}</option>
        {c.data?.colaboradores.filter((x) => k === 'motorista' || String(x.id) !== f.motorista).map((x) => (
          <option key={x.id} value={x.id}>{x.nome}{x.zona ? ` · ${x.zona}` : ''}{x.servicos_dia ? ` · ${x.servicos_dia} serv. no dia` : ''}{x.alertas.length ? ` · ⚠ ${x.alertas.join(', ')}` : ''}</option>
        ))}
      </select>)}</Field>
  )
  return (
    <Modal title="Atribuir viatura e motorista" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="rounded-lg bg-bg px-3.5 py-2.5 text-[13px] mb-4">
        <b className="font-semibold">{s.tipo_label}</b> em <b className="font-semibold">{s.loja}</b> · {dataCurta(s.data)}{s.hora_inicio ? `, ${s.hora_inicio}–${s.hora_fim ?? ''}` : ''}
      </div>
      {c.isLoading ? <Loading /> : (
        <div className="flex flex-col gap-3.5">
          <Field label="Viatura">{(id) => (
            <select id={id} className="inp" value={f.viatura} onChange={(e) => setF({ ...f, viatura: e.target.value })}>
              <option value="">Sem viatura</option>
              {c.data?.viaturas.map((v) => <option key={v.id} value={v.id}>{v.matricula}{v.descricao ? ` · ${v.descricao}` : ''}{v.servicos_dia ? ` · ${v.servicos_dia} serv. no dia` : ''}{v.conflito ? ' · ⚠ ocupada a essa hora' : ''}</option>)}
            </select>)}</Field>
          {colab('motorista', 'Motorista', 'Sem motorista')}
          {colab('ajudante', 'Ajudante (opcional)', 'Sem ajudante')}
          <p className="text-xs text-ink-60">Os avisos (ausência, outro serviço à mesma hora, indisponibilidade) não impedem a escolha.</p>
        </div>
      )}
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function ExecucaoDialog({ s, onClose }: { s: ServicoLog; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [f, setF] = useState({
    km_partida: s.km_partida != null ? String(s.km_partida) : '', km_chegada: s.km_chegada != null ? String(s.km_chegada) : '',
    portagens: s.portagens != null ? String(s.portagens).replace('.', ',') : '', outros_custos: s.outros_custos != null ? String(s.outros_custos).replace('.', ',') : '',
    outros_custos_desc: s.outros_custos_desc ?? '', inicio_real: s.inicio_real ?? s.hora_inicio ?? '', fim_real: s.fim_real ?? s.hora_fim ?? '',
    observacao: s.observacao_execucao ?? '',
  })
  const [ficheiro, setFicheiro] = useState<File | null>(null)
  const kmErr = f.km_partida && f.km_chegada && Number(f.km_chegada) < Number(f.km_partida) ? 'Inferior aos km de partida' : null
  const km = f.km_partida && f.km_chegada && !kmErr ? Number(f.km_chegada) - Number(f.km_partida) : null
  const m = useMutation({
    mutationFn: () => apiForm<ServicoLog>(`/servicos-logisticos/${s.id}/execucao`, 'POST', { ...f, comprovativo: ficheiro }),
    onSuccess: (r) => { invalidar(qc); toast(`Execução registada · custo ${eur(r.custos?.total ?? 0)}`); onClose() },
  })
  const t = (k: keyof typeof f, label: string, extra: Partial<React.InputHTMLAttributes<HTMLInputElement>> = {}, err?: string | null) => (
    <Field label={label} error={err}>{(id) => <input id={id} className={`inp num ${err ? 'inp-err' : ''}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} {...extra} />}</Field>
  )
  return (
    <Modal title={`Registar execução · ${s.loja}`} onClose={onClose} width={620}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!!kmErr} onClick={() => m.mutate()}>Guardar registo</Button></>}>
      <div className="rounded-lg bg-bg px-3.5 py-2.5 text-[13px] mb-4">
        {s.tipo_label} · {dataCurta(s.data)} · <Icon name="truck" size={13} className="inline -mt-0.5" /> {s.viatura?.split(' · ')[0]} · {s.colaborador}{s.ajudante ? ` + ${s.ajudante}` : ''}
      </div>
      <div className="grid grid-cols-2 gap-3.5">
        {t('km_partida', 'Km de partida', { inputMode: 'numeric' })}
        {t('km_chegada', 'Km de chegada', { inputMode: 'numeric' }, kmErr)}
        {t('inicio_real', 'Hora de início', { type: 'time' })}
        {t('fim_real', 'Hora de fim', { type: 'time' })}
        {t('portagens', 'Portagens (€)', { inputMode: 'decimal' })}
        {t('outros_custos', 'Outros custos (€)', { inputMode: 'decimal' })}
        <Field label="Descrição dos outros custos" className="col-span-2">{(id) => <input id={id} className="inp" value={f.outros_custos_desc} placeholder="Ex.: estacionamento, refeição" onChange={(e) => setF({ ...f, outros_custos_desc: e.target.value })} />}</Field>
        <Field label="Comprovativo (guia assinada, fotografia)" className="col-span-2" hint={s.comprovativo_nome ? `Atual: ${s.comprovativo_nome}` : 'PDF ou imagem, até 10 MB'}>{(id) => (
          <input id={id} type="file" accept="application/pdf,image/*" className="text-[13px]" onChange={(e) => setFicheiro(e.target.files?.[0] ?? null)} />)}</Field>
        <Field label="Observação" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacao} onChange={(e) => setF({ ...f, observacao: e.target.value })} />}</Field>
      </div>
      {km !== null && <p className="text-xs text-ink-60 mt-3 num">{km} km percorridos.</p>}
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function CancelarDialog({ s, onClose }: { s: ServicoLog; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [motivo, setMotivo] = useState('')
  const m = useMutation({
    mutationFn: () => api(`/servicos-logisticos/${s.id}/cancelar`, { method: 'POST', body: { motivo } }),
    onSuccess: () => { invalidar(qc); toast('Serviço cancelado', 'warn'); onClose() },
  })
  return (
    <Modal title={`Cancelar ${s.tipo_label.toLowerCase()} · ${s.loja}`} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Voltar</Button><Button variant="danger" loading={m.isPending} disabled={motivo.trim().length < 3} onClick={() => m.mutate()}>Cancelar serviço</Button></>}>
      <p className="text-[13px] text-ink-60 mb-3">O serviço fica no histórico como cancelado e deixa de ser faturado.</p>
      <Field label="Motivo">{(id) => <input id={id} className="inp" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}</Field>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

/** Criar ou editar um serviço de um contrato de Logística. */
export function ServicoDialog({ contratoId, contrato, s, onClose }: { contratoId: number; contrato?: Contrato; s?: ServicoLog; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [loja, setLoja] = useState<{ id: number; nome: string } | null>(s ? { id: s.loja_id, nome: s.loja } : null)
  const [f, setF] = useState({
    tipo: (s?.tipo ?? 'entrega') as TipoServicoLog, data: s?.data ?? '', hora_inicio: s?.hora_inicio ?? '', hora_fim: s?.hora_fim ?? '',
    origem: s?.origem ?? '', materiais: s?.materiais ?? '', preco: s ? String(s.preco).replace('.', ',') : '', referencia_erp: s?.referencia_erp ?? '',
    observacoes: s?.observacoes ?? '',
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value })
  const janelaErr = f.hora_inicio && f.hora_fim && f.hora_fim <= f.hora_inicio ? 'Tem de ser depois do início' : null
  const m = useMutation({
    mutationFn: () => api(s ? `/servicos-logisticos/${s.id}` : `/contratos/${contratoId}/servicos`, { method: s ? 'PUT' : 'POST', body: {
      loja_id: loja!.id, tipo: f.tipo, data: f.data, hora_inicio: f.hora_inicio || null, hora_fim: f.hora_fim || null, origem: f.origem || null,
      materiais: f.materiais || null, preco: Number(String(f.preco).replace(',', '.')) || 0, referencia_erp: f.referencia_erp || null,
      observacoes: f.observacoes || null } }),
    onSuccess: () => { invalidar(qc); toast(s ? 'Serviço atualizado' : 'Serviço criado'); onClose() },
  })
  return (
    <Modal title={s ? `Editar serviço · ${s.loja}` : 'Novo serviço logístico'} onClose={onClose} width={640}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!loja || !f.data || !!janelaErr} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Loja (destino)" className="col-span-2">{(id) => <LojaPicker id={id} value={loja} onChange={(l) => setLoja(l ? { id: l.id, nome: l.nome } : null)} />}</Field>
        <Field label="Serviço">{(id) => (
          <select id={id} className="inp" value={f.tipo} onChange={set('tipo')}>{TIPOS_LOG.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}</select>)}</Field>
        <Field label="Data">{(id) => <DataInput id={id} value={f.data} min={contrato?.inicio} max={contrato?.fim ?? undefined} onChange={(v) => setF({ ...f, data: v })} />}</Field>
        <Field label="Janela: das">{(id) => <input id={id} type="time" className="inp" value={f.hora_inicio} onChange={set('hora_inicio')} />}</Field>
        <Field label="às" error={janelaErr}>{(id) => <input id={id} type="time" className={`inp ${janelaErr ? 'inp-err' : ''}`} value={f.hora_fim} onChange={set('hora_fim')} />}</Field>
        <Field label="Origem">{(id) => <input id={id} className="inp" value={f.origem} placeholder="Ex.: Armazém Alverca" onChange={set('origem')} />}</Field>
        <Field label="Preço do serviço (€)">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.preco} onChange={set('preco')} />}</Field>
        <Field label="Materiais" className="col-span-2">{(id) => <textarea id={id} rows={2} className="inp !h-auto py-2" value={f.materiais} placeholder="Ex.: 2 expositores de chão; 50 cartazes A2" onChange={set('materiais')} />}</Field>
        <Field label="Referência no ERP">{(id) => <input id={id} className="inp" value={f.referencia_erp} placeholder="Pedido ou guia" onChange={set('referencia_erp')} />}</Field>
        <Field label="Observações">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={set('observacoes')} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

/** Grelha de serviços dentro do contrato de Logística. */
export function ServicosContrato({ contrato }: { contrato: Contrato }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['contrato-servicos', contrato.id], queryFn: () => api<ServicoLog[]>(`/contratos/${contrato.id}/servicos`) })
  const [novo, setNovo] = useState(false)
  const [verCancelados, setVerCancelados] = useState(false)
  const [atribuir, setAtribuir] = useState<ServicoLog | null>(null)
  const [executar, setExecutar] = useState<ServicoLog | null>(null)
  const [editar, setEditar] = useState<ServicoLog | null>(null)
  const [cancelar, setCancelar] = useState<ServicoLog | null>(null)
  const [detalhe, setDetalhe] = useState<ServicoLog | null>(null)
  const validar = useMutation({
    mutationFn: (ids: number[]) => api('/servicos-logisticos/validar', { method: 'POST', body: { ids, aprovar: true } }),
    onSuccess: () => { invalidar(qc); toast('Serviço validado') },
  })
  const hoje = iso(new Date())
  const itens = (q.data ?? []).filter((s) => verCancelados || s.estado !== 'cancelado')
  const cancelados = (q.data ?? []).filter((s) => s.estado === 'cancelado').length
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 bg-[#FAFBF9] border-b border-line-soft">
        <h3 className="text-[14.5px] font-semibold">Serviços</h3>
        <span className="text-[12.5px] text-ink-60">cada serviço é uma entrega, recolha ou implementação numa loja e data</span>
        <span className="flex-1" />
        {cancelados > 0 && <label className="flex items-center gap-2 text-[13px] text-ink-80 mr-2"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={verCancelados} onChange={(e) => setVerCancelados(e.target.checked)} />Mostrar cancelados ({cancelados})</label>}
        {podeContratos() && <Button size="sm" icon="plus" onClick={() => setNovo(true)}>Adicionar serviço</Button>}
      </div>
      {q.isLoading ? <Loading /> : !itens.length ? <Empty title="Sem serviços neste contrato">Adicione os serviços (loja, tipo, data, materiais e preço) ou importe os pedidos do ERP em Importar dados.</Empty> : (
        <div>{itens.map((s) => (
          <LinhaServico key={s.id} s={s} hoje={hoje} mostrarData onDetalhe={() => setDetalhe(s)} onAtribuir={() => setAtribuir(s)}
            onExecutar={() => setExecutar(s)} onEditar={() => setEditar(s)} onCancelar={() => setCancelar(s)} onValidar={() => validar.mutate([s.id])} />
        ))}</div>
      )}
      {contrato.estado === 'proposta' && <div className="px-4 py-3 border-t border-line text-[12.5px] text-warn-fg flex items-center gap-1.5"><Icon name="alert" size={14} />Ative o contrato para os serviços aparecerem na Logística.</div>}
      {novo && <ServicoDialog contratoId={contrato.id} contrato={contrato} onClose={() => setNovo(false)} />}
      {editar && <ServicoDialog contratoId={contrato.id} contrato={contrato} s={editar} onClose={() => setEditar(null)} />}
      {atribuir && <AtribuirDialog s={atribuir} onClose={() => setAtribuir(null)} />}
      {executar && <ExecucaoDialog s={executar} onClose={() => setExecutar(null)} />}
      {cancelar && <CancelarDialog s={cancelar} onClose={() => setCancelar(null)} />}
      {detalhe && <DetalheDialog s={detalhe} onClose={() => setDetalhe(null)} />}
    </>
  )
}

// ------------------------------------------------------------------ viaturas
function Viaturas() {
  const qc = useQueryClient()
  const toast = useToast()
  const [inativos, setInativos] = useState(false)
  const [edit, setEdit] = useState<Viatura | 'nova' | null>(null)
  const q = useQuery({ queryKey: ['viaturas', 'gestao', inativos], queryFn: () => api<Viatura[]>('/viaturas', { params: { inativos } }) })
  const estado = useMutation({
    mutationFn: (v: Viatura) => api(`/viaturas/${v.id}/estado`, { method: 'POST', body: { ativo: !v.ativo } }),
    onSuccess: (_, v) => { qc.invalidateQueries({ queryKey: ['viaturas'] }); toast(v.ativo ? 'Viatura desativada' : 'Viatura reativada', v.ativo ? 'warn' : 'ok') },
    onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })
  const pode = podeViaturas()
  return (
    <Card className="overflow-hidden max-w-[980px]">
      <div className="flex items-center gap-3 px-[18px] py-3 border-b border-line-soft">
        <h3 className="text-[14.5px] font-semibold">Viaturas</h3>
        <span className="text-[12.5px] text-ink-60">o custo por km entra no custo de cada serviço</span>
        <span className="flex-1" />
        <MostrarInativos value={inativos} onChange={setInativos} />
        {pode && <Button size="sm" variant="primary" icon="plus" onClick={() => setEdit('nova')}>Nova viatura</Button>}
      </div>
      {q.isLoading ? <Loading /> : !q.data?.length ? <Empty title="Sem viaturas" /> : (
        <table className="tbl">
          <thead><tr><th>Matrícula</th><th>Descrição</th><th className="text-right">Custo/km</th><th className="text-right">Serviços</th><th>Estado</th><th /></tr></thead>
          <tbody>{q.data.map((v) => (
            <tr key={v.id} className={v.ativo ? '' : 'opacity-60'}>
              <td className="font-medium font-mono">{v.matricula}</td>
              <td>{v.descricao ?? '—'}{v.observacoes && <div className="text-xs text-ink-60">{v.observacoes}</div>}</td>
              <td className="text-right num">{eur(v.custo_km, 3)}</td>
              <td className="text-right num">{v.servicos}</td>
              <td>{v.ativo ? <Badge tone="ok" dot>Ativa</Badge> : <Badge dot>Inativa</Badge>}</td>
              <td className="text-right whitespace-nowrap">{pode && <>
                <AcaoIcone icon="edit" label={`Editar ${v.matricula}`} onClick={() => setEdit(v)} />
                <AcaoIcone icon={v.ativo ? 'trash' : 'hist'} tom={v.ativo ? 'perigo' : 'neutro'} label={`${v.ativo ? 'Desativar' : 'Reativar'} ${v.matricula}`} onClick={() => estado.mutate(v)} />
              </>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {edit && <ViaturaDialog v={edit === 'nova' ? null : edit} onClose={() => setEdit(null)} />}
    </Card>
  )
}

function ViaturaDialog({ v, onClose }: { v: Viatura | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [f, setF] = useState({ matricula: v?.matricula ?? '', descricao: v?.descricao ?? '', custo_km: v ? String(v.custo_km).replace('.', ',') : '', observacoes: v?.observacoes ?? '' })
  const m = useMutation({
    mutationFn: () => api(v ? `/viaturas/${v.id}` : '/viaturas', { method: v ? 'PUT' : 'POST', body: {
      matricula: f.matricula, descricao: f.descricao || null, custo_km: Number(f.custo_km.replace(',', '.')) || 0, observacoes: f.observacoes || null } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['viaturas'] }); toast(v ? 'Viatura atualizada' : 'Viatura criada'); onClose() },
  })
  return (
    <Modal title={v ? `Editar ${v.matricula}` : 'Nova viatura'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={f.matricula.trim().length < 4} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Matrícula">{(id) => <input id={id} className="inp font-mono uppercase" value={f.matricula} placeholder="AA-12-BC" onChange={(e) => setF({ ...f, matricula: e.target.value })} />}</Field>
        <Field label="Custo por km (€)" hint="Combustível e desgaste">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.custo_km} placeholder="0,30" onChange={(e) => setF({ ...f, custo_km: e.target.value })} />}</Field>
        <Field label="Descrição" className="col-span-2">{(id) => <input id={id} className="inp" value={f.descricao} placeholder="Ex.: Renault Master · caixa fechada" onChange={(e) => setF({ ...f, descricao: e.target.value })} />}</Field>
        <Field label="Observações" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
