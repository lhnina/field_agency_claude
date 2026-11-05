import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AcaoIcone, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { DataInput, MesSeletor } from '../components/DataInput'
import { LojaPicker } from '../components/LojaPicker'
import { ColaboradorPicker } from '../components/ColaboradorPicker'
import { api, session } from '../lib/api'
import { addDays, dataCurta, diaMes, diaSemana, eur, horas, iso, intervaloSemana, segunda } from '../lib/format'
import type { Cliente, Contrato, DespesaEquipa, DiaEquipa, DiaEscala, ElementoEquipa, Equipa, EstadoDiaEquipa, RotaEquipa } from '../lib/types'

const DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
export const ESTADO_DIA: Record<EstadoDiaEquipa, { label: string; tone: 'neu' | 'info' | 'warn' | 'ok' | 'err' }> = {
  planeado: { label: 'Planeado', tone: 'info' }, validado: { label: 'Validado', tone: 'ok' }, falta: { label: 'Falta', tone: 'err' }, cancelado: { label: 'Cancelado', tone: 'neu' },
}
const perfil = () => session.user()?.perfil ?? ''
const podePlanear = () => ['administrador', 'gestor', 'gestor_conta', 'supervisor'].includes(perfil())
const podeContratos = () => ['administrador', 'gestor', 'gestor_conta'].includes(perfil())
const invalidar = (qc: ReturnType<typeof useQueryClient>) => ['equipas', 'equipa', 'contratos', 'contrato', 'prefaturacao', 'despesas', 'planeamento']
  .forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
const erroToast = (toast: ReturnType<typeof useToast>) => (e: unknown) => toast(e instanceof Error ? e.message : 'Erro', 'err')

type Linha = { elemento_id: number; colaborador_id: number; colaborador: string; funcao: string | null; contrato_id: number; contrato_numero: string; cliente: string; dias: Record<string, DiaEquipa>; horas: number }
type Semana = { inicio: string; fim: string; dias: string[]; linhas: Linha[]; resumo: { dias: number; por_validar: number; validados: number; faltas: number; substituicoes: number; com_alertas: number; horas: number; elementos: number } }

// ------------------------------------------------------------------ página: semana das equipas
export default function EquipasFixas() {
  const qc = useQueryClient()
  const toast = useToast()
  const [inicio, setInicio] = useState(() => iso(segunda(new Date())))
  const [cliente, setCliente] = useState('')
  const [dia, setDia] = useState<DiaEquipa | null>(null)
  const params = { inicio, cliente_id: cliente }
  const q = useQuery({ queryKey: ['equipas', params], queryFn: () => api<Semana>('/equipas/semana', { params }) })
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<Cliente[]>('/clientes') })
  const hoje = iso(new Date())
  const porValidar = (q.data?.linhas ?? []).flatMap((l) => Object.values(l.dias)).filter((d) => d.estado === 'planeado' && d.data <= hoje)
  const validar = useMutation({
    mutationFn: (ids: number[]) => api<{ validados: number }>('/servicos-equipa/validar', { method: 'POST', body: { ids } }),
    onSuccess: (r) => { invalidar(qc); toast(`${r.validados} dia(s) validado(s)`) },
    onError: erroToast(toast),
  })
  const r = q.data?.resumo
  return (
    <>
      <PageHeader crumb="Operação" title="Equipas fixas" sub="Colaboradores dedicados a um cliente, em rotas de lojas. Valide os dias trabalhados e registe faltas e substituições." />
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
          <div className="flex items-center gap-1">
            <AcaoIcone icon="cl" label="Semana anterior" onClick={() => setInicio(iso(addDays(new Date(inicio), -7)))} />
            <Button size="sm" variant="secondary" onClick={() => setInicio(iso(segunda(new Date())))}>Esta semana</Button>
            <AcaoIcone icon="cr" label="Semana seguinte" onClick={() => setInicio(iso(addDays(new Date(inicio), 7)))} />
          </div>
          {q.data && <span className="text-[13.5px] font-semibold ml-1">{intervaloSemana(q.data.inicio, q.data.fim)}</span>}
          <span className="flex-1" />
          <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">Cliente
            <select aria-label="Cliente" className="outline-none font-medium text-ink bg-transparent max-w-[220px]" value={cliente} onChange={(e) => setCliente(e.target.value)}>
              <option value="">Todos</option>{clientes.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select></label>
        </div>
        {r && (
          <div className="grid grid-cols-2 md:grid-cols-6 border-b border-line-soft">
            {[
              ['Colaboradores', String(r.elementos), 'em equipas nesta semana', ''],
              ['Dias de trabalho', String(r.dias), `${horas(Math.round(r.horas * 10) / 10)} planeadas`, ''],
              ['Por validar', String(r.por_validar), 'dias já passados', r.por_validar ? 'text-warn-fg' : ''],
              ['Validados', String(r.validados), 'contam para custo e fatura', ''],
              ['Faltas', String(r.faltas), 'não trabalhados', r.faltas ? 'text-err-fg' : ''],
              ['Substituições', String(r.substituicoes), `${r.com_alertas} dia(s) com alertas`, ''],
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
            <Icon name="alert" size={16} />{porValidar.length} dia(s) já passados por validar. Validar confirma as horas planeadas; para outras horas ou faltas, abra o dia.
            <span className="flex-1" />
            <Button size="sm" variant="subtil" icon="check" loading={validar.isPending} onClick={() => validar.mutate(porValidar.map((d) => d.id))}>Validar todos</Button>
          </div>
        )}
        {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : !q.data?.linhas.length ? (
          <Empty title="Sem equipas fixas nesta semana">As equipas criam-se num contrato de Equipas Fixas (Contratos › Novo contrato): rotas de lojas, colaboradores e a escala semanal.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th className="min-w-[200px]">Colaborador</th>
                {q.data.dias.map((d, i) => <th key={d} className={`min-w-[132px] ${d === hoje ? '!text-petrol-700' : ''}`}>{DIAS[i]} {diaMes(d)}</th>)}
                <th className="text-right">Horas</th></tr></thead>
              <tbody>
                {q.data.linhas.map((l) => (
                  <tr key={l.elemento_id}>
                    <td>
                      <div className="font-medium text-[13.5px]">{l.colaborador}</div>
                      <div className="text-xs text-ink-60"><Link to={`/contratos/${l.contrato_id}`} className="hover:underline">{l.cliente}</Link> · <span className="font-mono">{l.contrato_numero}</span></div>
                    </td>
                    {q.data!.dias.map((d) => {
                      const x = l.dias[d]
                      if (!x) return <td key={d} className="text-ink-60 text-xs">—</td>
                      return (
                        <td key={d} className={d === hoje ? 'bg-petrol-50/40' : ''}>
                          <button type="button" onClick={() => setDia(x)} aria-label={`${l.colaborador}, ${diaSemana(d)} ${diaMes(d)}`}
                            className={`w-full text-left rounded-md border px-2 py-1.5 hover:border-petrol-600 ${x.estado === 'falta' ? 'border-err/40 bg-err-bg/40' : x.estado === 'validado' ? 'border-ok/30 bg-ok-bg/40' : 'border-line bg-white'}`}>
                            <div className="text-[12.5px] font-medium truncate">{x.rota ?? 'Sem rota'}</div>
                            <div className="text-[11.5px] text-ink-60 num">{x.estado === 'falta' ? 'Falta' : `${x.hora_inicio}–${x.hora_fim} · ${horas(x.horas_reais ?? x.horas_planeadas)}`}</div>
                            <div className="flex items-center gap-1 mt-0.5">
                              {x.estado === 'validado' && <Icon name="check" size={13} className="text-ok-fg" />}
                              {x.substituicao && <span className="text-[11px] text-petrol-700 truncate">↺ {x.colaborador}</span>}
                              {x.alertas.length > 0 && <span className="ml-auto text-warn-fg" title={x.alertas.join('\n')}><Icon name="alert" size={13} /></span>}
                            </div>
                          </button>
                        </td>
                      )
                    })}
                    <td className="text-right num">{horas(Math.round(l.horas * 10) / 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="text-[12.5px] text-ink-60 flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />
        Fatura-se o custo real de cada colaborador (horas validadas × custo/hora com encargos), mais o valor de gestão mensal e as despesas refaturadas. Um mês só fecha com todos os dias validados ou com falta registada.</p>
      {dia && <DiaDialog d={dia} onClose={() => setDia(null)} />}
    </>
  )
}

// ------------------------------------------------------------------ um dia de trabalho
function DiaDialog({ d, onClose }: { d: DiaEquipa; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const equipa = useQuery({ queryKey: ['equipa', d.contrato_id], queryFn: () => api<Equipa>(`/contratos/${d.contrato_id}/equipa`) })
  const [col, setCol] = useState<{ id: number; nome: string } | null>({ id: d.colaborador_id, nome: d.colaborador })
  const [f, setF] = useState({ rota_id: d.rota_id ? String(d.rota_id) : '', hora_inicio: d.hora_inicio, hora_fim: d.hora_fim, pausa_min: String(d.pausa_min), observacao: d.observacao ?? '' })
  const [horasReais, setHorasReais] = useState(String(d.horas_reais ?? d.horas_planeadas).replace('.', ','))
  const [motivo, setMotivo] = useState('')
  const [modo, setModo] = useState<'dia' | 'falta'>('dia')
  const hoje = iso(new Date())
  const feito = (msg: string) => () => { invalidar(qc); toast(msg); onClose() }
  const guardar = useMutation({
    mutationFn: () => api(`/servicos-equipa/${d.id}`, { method: 'PUT', body: { colaborador_id: col?.id, rota_id: f.rota_id ? Number(f.rota_id) : null, hora_inicio: f.hora_inicio, hora_fim: f.hora_fim, pausa_min: Number(f.pausa_min) || 0, observacao: f.observacao || null } }),
    onSuccess: feito('Dia atualizado'), onError: erroToast(toast),
  })
  const validar = useMutation({
    mutationFn: () => api('/servicos-equipa/validar', { method: 'POST', body: { ids: [d.id], horas: Number(horasReais.replace(',', '.')) } }),
    onSuccess: feito('Dia validado'), onError: erroToast(toast),
  })
  const falta = useMutation({ mutationFn: () => api(`/servicos-equipa/${d.id}/falta`, { method: 'POST', body: { motivo } }), onSuccess: feito('Falta registada'), onError: erroToast(toast) })
  const repor = useMutation({ mutationFn: () => api(`/servicos-equipa/${d.id}/repor`, { method: 'POST' }), onSuccess: feito('Dia reaberto'), onError: erroToast(toast) })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })
  const editavel = d.estado === 'planeado' && podePlanear()
  return (
    <Modal title={`${d.titular} · ${diaSemana(d.data)}, ${diaMes(d.data)}`} onClose={onClose} width={600}
      footer={editavel ? (modo === 'falta'
        ? <><Button variant="ghost" onClick={() => setModo('dia')}>Voltar</Button><Button variant="danger" disabled={motivo.trim().length < 2} loading={falta.isPending} onClick={() => falta.mutate()}>Registar falta</Button></>
        : <><Button variant="ghost" className="mr-auto" onClick={() => setModo('falta')}>Registar falta</Button>
          <Button onClick={() => guardar.mutate()} loading={guardar.isPending} disabled={!col}>Guardar alterações</Button>
          {d.data <= hoje && <Button variant="primary" icon="check" loading={validar.isPending} onClick={() => validar.mutate()}>Validar</Button>}</>)
        : <>{podePlanear() && d.estado !== 'cancelado' && <Button variant="ghost" className="mr-auto" loading={repor.isPending} onClick={() => repor.mutate()}>{d.estado === 'falta' ? 'Anular falta' : 'Reabrir para corrigir'}</Button>}<Button onClick={onClose}>Fechar</Button></>}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <Badge tone={ESTADO_DIA[d.estado].tone} dot>{ESTADO_DIA[d.estado].label}</Badge>
        <span className="text-[12.5px] text-ink-60">{d.cliente} · <span className="font-mono">{d.contrato_numero}</span></span>
        {d.substituicao && <Badge tone="info">Substituição: {d.colaborador}</Badge>}
      </div>
      {d.alertas.length > 0 && <div className="rounded-lg bg-warn-bg text-[#6B4000] px-3 py-2 text-[12.5px] mb-3 flex flex-col gap-0.5">{d.alertas.map((a) => <div key={a} className="flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />{a}</div>)}</div>}
      {d.lojas.length > 0 && <div className="text-[12.5px] text-ink-60 mb-3">Lojas da rota: {d.lojas.join(' → ')}</div>}
      {!editavel ? (
        <div className="grid grid-cols-2 gap-3 text-[13.5px]">
          <div><div className="text-xs text-ink-60">Horário</div>{d.hora_inicio}–{d.hora_fim} (pausa {d.pausa_min} min)</div>
          <div><div className="text-xs text-ink-60">Horas</div>{d.estado === 'falta' ? '0 h' : horas(d.horas_reais ?? d.horas_planeadas)}</div>
          {d.observacao && <div className="col-span-2"><div className="text-xs text-ink-60">Observação</div>{d.observacao}</div>}
        </div>
      ) : modo === 'falta' ? (
        <Field label="Motivo da falta" hint="O dia fica com 0 horas: não conta para custo, faturação nem remuneração">{(id) => <input id={id} className="inp" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: doença, férias" autoFocus />}</Field>
      ) : (
        <div className="grid grid-cols-2 gap-3.5">
          <Field label="Quem faz o dia" hint="Escolha outro colaborador para uma substituição" className="col-span-2">{(id) => <ColaboradorPicker id={id} value={col} onChange={(c) => setCol(c ? { id: c.id, nome: c.nome } : null)} />}</Field>
          <Field label="Rota" className="col-span-2">{(id) => <select id={id} className="inp" value={f.rota_id} onChange={set('rota_id')}>{equipa.data?.rotas.filter((r) => r.ativo || String(r.id) === f.rota_id).map((r) => <option key={r.id} value={r.id}>{r.nome}</option>)}</select>}</Field>
          <div className="col-span-2 grid grid-cols-3 gap-3.5">
            <Field label="Início">{(id) => <input id={id} type="time" className="inp num" value={f.hora_inicio} onChange={set('hora_inicio')} />}</Field>
            <Field label="Fim">{(id) => <input id={id} type="time" className="inp num" value={f.hora_fim} onChange={set('hora_fim')} />}</Field>
            <Field label="Pausa (min)">{(id) => <input id={id} inputMode="numeric" className="inp num" value={f.pausa_min} onChange={set('pausa_min')} />}</Field>
          </div>
          <Field label="Observação" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacao} onChange={set('observacao')} />}</Field>
          {d.data <= hoje && <Field label="Horas a validar" hint="Por omissão, as horas planeadas">{(id) => <input id={id} inputMode="decimal" className="inp num" value={horasReais} onChange={(e) => setHorasReais(e.target.value)} />}</Field>}
        </div>
      )}
    </Modal>
  )
}

// ------------------------------------------------------------------ no contrato: equipa, rotas e despesas
export function EquipaContrato({ contrato }: { contrato: Contrato }) {
  const [tab, setTab] = useState<'equipa' | 'rotas' | 'despesas'>('equipa')
  const q = useQuery({ queryKey: ['equipa', contrato.id], queryFn: () => api<Equipa>(`/contratos/${contrato.id}/equipa`) })
  return (
    <>
      <div className="flex items-center gap-0.5 px-[18px] border-b border-line bg-[#FAFBF9]" role="tablist" aria-label="Equipa fixa">
        {([['equipa', `Equipa (${q.data?.elementos.length ?? 0})`], ['rotas', `Rotas (${q.data?.rotas.filter((r) => r.ativo).length ?? 0})`], ['despesas', 'Despesas']] as const).map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`h-10 px-3 text-[13.5px] -mb-px border-b-2 ${tab === k ? 'border-petrol-600 text-ink font-medium' : 'border-transparent text-ink-60 hover:text-ink'}`}>{l}</button>
        ))}
      </div>
      {q.isLoading ? <Loading /> : q.error || !q.data ? <div className="p-4"><ErrorBox error={q.error} /></div>
        : tab === 'equipa' ? <Elementos contrato={contrato} eq={q.data} onRotas={() => setTab('rotas')} />
        : tab === 'rotas' ? <Rotas contrato={contrato} eq={q.data} /> : <Despesas contrato={contrato} eq={q.data} />}
      {contrato.estado === 'proposta' && <div className="px-4 py-3 border-t border-line text-[12.5px] text-warn-fg flex items-center gap-1.5"><Icon name="alert" size={14} />Passe o contrato a Em curso para gerar os dias de trabalho a partir da escala.</div>}
    </>
  )
}

function Elementos({ contrato, eq, onRotas }: { contrato: Contrato; eq: Equipa; onRotas: () => void }) {
  const [edit, setEdit] = useState<ElementoEquipa | 'novo' | null>(null)
  const hoje = iso(new Date())
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
        <span className="text-[12.5px] text-ink-60">Cada colaborador tem uma escala semanal: a rota e o horário de cada dia.</span>
        <span className="flex-1" />
        {podeContratos() && <Button size="sm" icon="plus" disabled={!eq.rotas.some((r) => r.ativo)} onClick={() => setEdit('novo')}>Acrescentar colaborador</Button>}
      </div>
      {!eq.rotas.some((r) => r.ativo) && <div className="px-4 py-3 text-[13px] text-ink-80 flex items-center gap-2"><Icon name="alert" size={16} className="text-warn-fg" />Crie primeiro as rotas (as lojas que a equipa visita).<Button size="sm" variant="subtil" onClick={onRotas}>Ir para Rotas</Button></div>}
      {!eq.elementos.length ? <Empty title="Sem colaboradores na equipa" /> : (
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Colaborador</th><th>Período</th>{DIAS.map((d) => <th key={d}>{d}</th>)}<th className="text-right">H/semana</th><th className="text-right">Gestão/mês</th><th /></tr></thead>
            <tbody>
              {eq.elementos.map((el) => {
                const terminado = !!el.ate && el.ate < hoje
                return (
                  <tr key={el.id} className={terminado ? 'opacity-60' : ''}>
                    <td><button type="button" className="font-medium text-[13.5px] hover:text-petrol-600 hover:underline text-left" onClick={() => podeContratos() && setEdit(el)}>{el.colaborador}</button>
                      <div className="text-xs text-ink-60">N.º {el.numero}{el.funcao ? ` · ${el.funcao}` : ''}</div></td>
                    <td className="text-[12.5px] num whitespace-nowrap">{dataCurta(el.desde)} – {el.ate ? dataCurta(el.ate) : 'sem fim'}{terminado && <div><Badge>Terminado</Badge></div>}</td>
                    {DIAS.map((_d, i) => {
                      const e = el.escala.find((x) => x.dia === i)
                      return <td key={i} className="text-[12px] min-w-[96px]">{e ? <><div className="font-medium truncate max-w-[120px]" title={e.rota}>{e.rota}</div><div className="text-ink-60 num">{e.hora_inicio}–{e.hora_fim}</div></> : <span className="text-ink-60">—</span>}</td>
                    })}
                    <td className="text-right num">{horas(el.horas_semana)}</td>
                    <td className="text-right num">{eur(el.valor_gestao_efetivo)}{el.valor_gestao == null && <div className="text-[11px] text-ink-60">do contrato</div>}</td>
                    <td className="text-right">{podeContratos() && <AcaoIcone icon="edit" label={`Editar ${el.colaborador}`} onClick={() => setEdit(el)} />}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="px-4 py-2.5 border-t border-line-soft text-[12.5px] text-ink-60">
        {eq.resumo.elementos} colaborador(es) · {horas(eq.resumo.horas_semana)}/semana · gestão {eur(eq.resumo.gestao_mensal)}/mês
        {eq.valor_gestao != null ? ` (valor por omissão ${eur(eq.valor_gestao)})` : ' · sem valor de gestão no contrato'}
      </div>
      {edit && <ElementoDialog contrato={contrato} eq={eq} el={edit === 'novo' ? null : edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function ElementoDialog({ contrato, eq, el, onClose }: { contrato: Contrato; eq: Equipa; el: ElementoEquipa | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const hoje = iso(new Date())
  const rotas = eq.rotas.filter((r) => r.ativo)
  const [col, setCol] = useState<{ id: number; nome: string } | null>(el ? { id: el.colaborador_id, nome: el.colaborador } : null)
  const [f, setF] = useState({
    desde: el?.desde ?? (contrato.inicio > hoje ? contrato.inicio : hoje), ate: el?.ate ?? '',
    valor_gestao: el?.valor_gestao != null ? String(el.valor_gestao) : '', observacoes: el?.observacoes ?? '',
  })
  const [escala, setEscala] = useState<(DiaEscala & { on: boolean })[]>(() => DIAS.map((_d, i) => {
    const e = el?.escala.find((x) => x.dia === i)
    return e ? { ...e, on: true } : { dia: i, rota_id: rotas[0]?.id ?? 0, hora_inicio: '09:00', hora_fim: '18:00', pausa_min: 60, on: !el && i < 5 }
  }))
  const setDia = (i: number, p: Partial<DiaEscala & { on: boolean }>) => setEscala((s) => s.map((x) => (x.dia === i ? { ...x, ...p } : x)))
  const total = escala.filter((e) => e.on).reduce((s, e) => {
    const [a, b] = [e.hora_inicio, e.hora_fim].map((h) => Number(h.slice(0, 2)) * 60 + Number(h.slice(3, 5)))
    return s + Math.max(0, (b > a ? b - a : b + 1440 - a) - (Number(e.pausa_min) || 0)) / 60
  }, 0)
  const m = useMutation({
    mutationFn: () => api<ElementoEquipa>(el ? `/elementos-equipa/${el.id}` : `/contratos/${contrato.id}/elementos`, {
      method: el ? 'PUT' : 'POST',
      body: { colaborador_id: col?.id, desde: f.desde, ate: f.ate || null, observacoes: f.observacoes || null,
        valor_gestao: f.valor_gestao.trim() ? Number(f.valor_gestao.replace(',', '.')) : null,
        escala: escala.filter((e) => e.on).map(({ dia, rota_id, hora_inicio, hora_fim, pausa_min }) => ({ dia, rota_id: Number(rota_id), hora_inicio, hora_fim, pausa_min: Number(pausa_min) || 0 })) },
    }),
    onSuccess: () => { invalidar(qc); toast(el ? 'Escala atualizada: os dias futuros foram refeitos' : 'Colaborador acrescentado à equipa'); onClose() },
  })
  return (
    <Modal title={el ? `${el.colaborador} · escala` : 'Acrescentar colaborador à equipa'} onClose={onClose} width={760}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!col || !f.desde} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-4 gap-3.5">
        <Field label="Colaborador" className="col-span-2">{(id) => el ? <input id={id} className="inp" value={el.colaborador} disabled /> : <ColaboradorPicker id={id} value={col} onChange={(c) => setCol(c ? { id: c.id, nome: c.nome } : null)} />}</Field>
        <Field label="Desde">{(id) => <DataInput id={id} value={f.desde} min={contrato.inicio} onChange={(v) => setF({ ...f, desde: v })} />}</Field>
        <Field label="Até" hint="Vazio = sem fim">{(id) => <DataInput id={id} limpar value={f.ate} min={f.desde} onChange={(v) => setF({ ...f, ate: v })} />}</Field>
        <Field label="Valor de gestão (€/mês)" hint={`Vazio = o do contrato${eq.valor_gestao != null ? ` (${eur(eq.valor_gestao)})` : ''}`} className="col-span-2">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.valor_gestao} onChange={(e) => setF({ ...f, valor_gestao: e.target.value })} />}</Field>
        <Field label="Observações" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      <div className="mt-4">
        <div className="flex items-center justify-between mb-1.5"><span className="lbl">Escala semanal</span><span className="text-[12.5px] text-ink-60 num">{horas(Math.round(total * 10) / 10)} por semana</span></div>
        <div className="border border-line rounded-lg divide-y divide-line-soft">
          {escala.map((e) => (
            <div key={e.dia} className={`grid grid-cols-[80px_1fr_118px_118px_84px] gap-2 items-center px-3 py-2 ${e.on ? '' : 'bg-[#FAFBF9]'}`}>
              <label className="flex items-center gap-2 text-[13px] font-medium"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={e.on} onChange={(x) => setDia(e.dia, { on: x.target.checked })} />{DIAS[e.dia]}</label>
              <select aria-label={`Rota de ${DIAS[e.dia]}`} className="inp" disabled={!e.on} value={e.rota_id} onChange={(x) => setDia(e.dia, { rota_id: Number(x.target.value) })}>
                {rotas.map((r) => <option key={r.id} value={r.id}>{r.nome}</option>)}
              </select>
              <input aria-label={`Início de ${DIAS[e.dia]}`} type="time" className="inp num" disabled={!e.on} value={e.hora_inicio} onChange={(x) => setDia(e.dia, { hora_inicio: x.target.value })} />
              <input aria-label={`Fim de ${DIAS[e.dia]}`} type="time" className="inp num" disabled={!e.on} value={e.hora_fim} onChange={(x) => setDia(e.dia, { hora_fim: x.target.value })} />
              <label className="flex items-center gap-1 text-xs text-ink-60"><input aria-label={`Pausa de ${DIAS[e.dia]}`} inputMode="numeric" className="inp num !px-2" disabled={!e.on} value={e.pausa_min} onChange={(x) => setDia(e.dia, { pausa_min: Number(x.target.value.replace(/\D/g, '')) })} />min</label>
            </div>
          ))}
        </div>
        <div className="text-xs text-ink-60 mt-1.5">Os feriados (nacionais e da zona do colaborador) não geram dia de trabalho. Mudar a escala refaz os dias futuros, mas mantém os que já foram alterados à mão.</div>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function Rotas({ contrato, eq }: { contrato: Contrato; eq: Equipa }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [edit, setEdit] = useState<RotaEquipa | 'nova' | null>(null)
  const estado = useMutation({
    mutationFn: (r: RotaEquipa) => api(`/rotas-equipa/${r.id}/estado`, { method: 'POST', body: { ativo: !r.ativo } }),
    onSuccess: () => { invalidar(qc); toast('Rota atualizada') }, onError: erroToast(toast),
  })
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
        <span className="text-[12.5px] text-ink-60">Uma rota é o conjunto de lojas visitadas num dia, pela ordem indicada.</span>
        <span className="flex-1" />
        {podeContratos() && <Button size="sm" icon="plus" onClick={() => setEdit('nova')}>Nova rota</Button>}
      </div>
      {!eq.rotas.length ? <Empty title="Sem rotas" /> : (
        <table className="tbl">
          <thead><tr><th>Rota</th><th>Lojas</th><th>Observações</th><th /></tr></thead>
          <tbody>{eq.rotas.map((r) => (
            <tr key={r.id} className={r.ativo ? '' : 'opacity-60'}>
              <td className="font-medium text-[13.5px] whitespace-nowrap"><button type="button" className="hover:text-petrol-600 hover:underline" onClick={() => podeContratos() && setEdit(r)}>{r.nome}</button>{!r.ativo && <span className="ml-2"><Badge>Inativa</Badge></span>}</td>
              <td className="text-[12.5px]">{r.lojas.map((l) => l.nome).join(' → ')}<div className="text-xs text-ink-60">{r.lojas.length} loja(s)</div></td>
              <td className="text-[12.5px] text-ink-60">{r.observacoes ?? '—'}</td>
              <td className="text-right whitespace-nowrap">{podeContratos() && <>
                <AcaoIcone icon="edit" label={`Editar ${r.nome}`} onClick={() => setEdit(r)} />
                {r.ativo ? <AcaoIcone icon="trash" tom="perigo" label={`Desativar ${r.nome}`} loading={estado.isPending} onClick={() => estado.mutate(r)} />
                  : <AcaoIcone icon="sync" label={`Reativar ${r.nome}`} onClick={() => estado.mutate(r)} />}
              </>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {edit && <RotaDialog contrato={contrato} r={edit === 'nova' ? null : edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function RotaDialog({ contrato, r, onClose }: { contrato: Contrato; r: RotaEquipa | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [nome, setNome] = useState(r?.nome ?? '')
  const [obs, setObs] = useState(r?.observacoes ?? '')
  const [lojas, setLojas] = useState<{ id: number; nome: string }[]>(r?.lojas ?? [])
  const mover = (i: number, d: number) => setLojas((s) => { const n = [...s]; const [x] = n.splice(i, 1); n.splice(i + d, 0, x); return n })
  const m = useMutation({
    mutationFn: () => api(r ? `/rotas-equipa/${r.id}` : `/contratos/${contrato.id}/rotas`, { method: r ? 'PUT' : 'POST', body: { nome, observacoes: obs || null, lojas: lojas.map((l) => l.id) } }),
    onSuccess: () => { invalidar(qc); toast(r ? 'Rota atualizada' : 'Rota criada'); onClose() },
  })
  return (
    <Modal title={r ? `Editar ${r.nome}` : 'Nova rota'} onClose={onClose} width={600}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!nome.trim() || !lojas.length} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-1 gap-3.5">
        <Field label="Nome da rota">{(id) => <input id={id} className="inp" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Rota Lisboa Centro" />}</Field>
        <Field label="Acrescentar loja" hint="As lojas ficam pela ordem da visita">{(id) => <LojaPicker id={id} value={null} usadas={new Set(lojas.map((l) => l.id))}
          onChange={(l) => l && !lojas.some((x) => x.id === l.id) && setLojas([...lojas, { id: l.id, nome: l.nome }])} />}</Field>
        {lojas.length > 0 && (
          <ol className="border border-line rounded-lg divide-y divide-line-soft">
            {lojas.map((l, i) => (
              <li key={l.id} className="flex items-center gap-2 px-3 py-1.5 text-[13.5px]">
                <span className="w-5 text-ink-60 num">{i + 1}.</span><span className="flex-1">{l.nome}</span>
                <AcaoIcone icon="cl" className="rotate-90" label={`Subir ${l.nome}`} disabled={i === 0} onClick={() => mover(i, -1)} />
                <AcaoIcone icon="cr" className="rotate-90" label={`Descer ${l.nome}`} disabled={i === lojas.length - 1} onClick={() => mover(i, 1)} />
                <AcaoIcone icon="trash" tom="perigo" label={`Retirar ${l.nome}`} onClick={() => setLojas(lojas.filter((x) => x.id !== l.id))} />
              </li>
            ))}
          </ol>
        )}
        <Field label="Observações">{(id) => <input id={id} className="inp" value={obs} onChange={(e) => setObs(e.target.value)} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

type ListaDespesas = { mes: string; itens: DespesaEquipa[]; tipos: Record<string, string>; totais: { custo: number; refaturado: number }; bloqueio: string | null }

function Despesas({ contrato, eq }: { contrato: Contrato; eq: Equipa }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [mes, setMes] = useState(() => iso(new Date()).slice(0, 7))
  const [edit, setEdit] = useState<DespesaEquipa | 'nova' | null>(null)
  const q = useQuery({ queryKey: ['despesas', contrato.id, mes], queryFn: () => api<ListaDespesas>(`/contratos/${contrato.id}/despesas`, { params: { mes: `${mes}-01` } }) })
  const apagar = useMutation({
    mutationFn: (d: DespesaEquipa) => api(`/despesas-equipa/${d.id}`, { method: 'DELETE' }),
    onSuccess: () => { invalidar(qc); toast('Despesa apagada') }, onError: erroToast(toast),
  })
  const pode = podeContratos() && !q.data?.bloqueio
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
        <MesSeletor value={mes} onChange={setMes} />
        <span className="text-[12.5px] text-ink-60">Viatura, combustível, portagens, telemóvel… As refaturadas vão para a fatura com {eq.acrescimo_despesas_pct ? `${eq.acrescimo_despesas_pct} % de acréscimo` : 'o mesmo valor'}.</span>
        <span className="flex-1" />
        {pode && <Button size="sm" icon="plus" onClick={() => setEdit('nova')}>Registar despesa</Button>}
      </div>
      {q.data?.bloqueio && <div className="px-4 py-2 text-[12.5px] text-ink-60 flex items-center gap-1.5 border-b border-line-soft"><Icon name="alert" size={14} />{q.data.bloqueio}</div>}
      {q.isLoading ? <Loading /> : !q.data?.itens.length ? <Empty title="Sem despesas neste mês" /> : (
        <table className="tbl">
          <thead><tr><th>Data</th><th>Tipo</th><th>Descrição</th><th>Colaborador</th><th>Refaturar</th><th className="text-right">Valor</th><th /></tr></thead>
          <tbody>{q.data.itens.map((d) => (
            <tr key={d.id}>
              <td className="num text-[12.5px]">{dataCurta(d.data)}</td><td>{d.tipo_label}</td>
              <td className="text-[12.5px]">{d.descricao ?? '—'}</td><td className="text-[12.5px] text-ink-60">{d.colaborador ?? '—'}</td>
              <td>{d.refaturar ? <Badge tone="ok">Sim</Badge> : <Badge>Só custo</Badge>}</td>
              <td className="text-right num">{eur(d.valor)}</td>
              <td className="text-right whitespace-nowrap">{pode && <>
                <AcaoIcone icon="edit" label="Editar despesa" onClick={() => setEdit(d)} />
                <AcaoIcone icon="trash" tom="perigo" label="Apagar despesa" loading={apagar.isPending} onClick={() => apagar.mutate(d)} />
              </>}</td>
            </tr>
          ))}</tbody>
          <tfoot><tr className="[&>td]:border-t [&>td]:border-line [&>td]:font-semibold">
            <td className="px-3 py-2.5" colSpan={5}>Total · a refaturar {eur(q.data.totais.refaturado)}</td>
            <td className="text-right num px-3">{eur(q.data.totais.custo)}</td><td />
          </tr></tfoot>
        </table>
      )}
      {edit && <DespesaDialog contrato={contrato} eq={eq} tipos={q.data?.tipos ?? {}} mes={mes} d={edit === 'nova' ? null : edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function DespesaDialog({ contrato, eq, tipos, mes, d, onClose }: { contrato: Contrato; eq: Equipa; tipos: Record<string, string>; mes: string; d: DespesaEquipa | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const hoje = iso(new Date())
  const [f, setF] = useState({
    data: d?.data ?? (hoje.startsWith(mes) ? hoje : `${mes}-01`), tipo: d?.tipo ?? 'combustivel', descricao: d?.descricao ?? '',
    valor: d ? String(d.valor).replace('.', ',') : '', elemento_id: d?.elemento_id ? String(d.elemento_id) : '', refaturar: d?.refaturar ?? true,
  })
  const m = useMutation({
    mutationFn: () => api(d ? `/despesas-equipa/${d.id}` : `/contratos/${contrato.id}/despesas`, {
      method: d ? 'PUT' : 'POST',
      body: { ...f, valor: Number(f.valor.replace(',', '.')), elemento_id: f.elemento_id ? Number(f.elemento_id) : null, descricao: f.descricao || null },
    }),
    onSuccess: () => { invalidar(qc); toast(d ? 'Despesa atualizada' : 'Despesa registada'); onClose() },
  })
  return (
    <Modal title={d ? 'Editar despesa' : 'Registar despesa'} onClose={onClose} width={520}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!Number(f.valor.replace(',', '.'))} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Data">{(id) => <DataInput id={id} value={f.data} min={contrato.inicio} onChange={(v) => setF({ ...f, data: v })} />}</Field>
        <Field label="Tipo">{(id) => <select id={id} className="inp" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>{Object.entries(tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Field>
        <Field label="Valor (€)">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.valor} onChange={(e) => setF({ ...f, valor: e.target.value })} />}</Field>
        <Field label="Colaborador" hint="Opcional">{(id) => <select id={id} className="inp" value={f.elemento_id} onChange={(e) => setF({ ...f, elemento_id: e.target.value })}><option value="">— (equipa)</option>{eq.elementos.map((el) => <option key={el.id} value={el.id}>{el.colaborador}</option>)}</select>}</Field>
        <Field label="Descrição" className="col-span-2">{(id) => <input id={id} className="inp" value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} />}</Field>
        <label className="col-span-2 flex items-center gap-2 text-[13.5px]"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={f.refaturar} onChange={(e) => setF({ ...f, refaturar: e.target.checked })} />Refaturar ao cliente{eq.acrescimo_despesas_pct ? ` (+${eq.acrescimo_despesas_pct} %)` : ''}</label>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
