import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AreaBadge, Avatar, Badge, Button, Card, ErrorBox, Icon, IconButton, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { api } from '../lib/api'
import { AREA, addDays, diaMes, diaSemana, horas, iso, intervaloSemana, parseISO, segunda, semanaISO, VINCULO } from '../lib/format'
import type { Candidato, Cliente, IdNome, LinhaColaborador, Ocorrencia, Planeamento as Plan } from '../lib/types'

type Drop = { oc: Ocorrencia; colaboradorId: number; data: string }

const ALERTA: Record<string, string> = {
  sem_colaborador: 'Sem colaborador',
  colaborador_ausente: 'Colaborador ausente nesta data',
  excede_horas_dia: 'Excede 8 h no dia',
  documentacao: 'Documentação em falta ou expirada',
}

export default function Planeamento() {
  const qc = useQueryClient()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const [inicio, setInicio] = useState(() => iso(segunda(new Date())))
  const [tipo, setTipo] = useState<string>('')
  const [zona, setZona] = useState(sp.get('zona') ?? '')
  const colaborador = sp.get('colaborador') ?? ''
  const limparColaborador = () => { sp.delete('colaborador'); sp.delete('zona'); setSp(sp, { replace: true }) }
  const [cliente, setCliente] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const [drop, setDrop] = useState<Drop | null>(null)
  const [subst, setSubst] = useState<Ocorrencia | null>(null)
  const [dragOver, setDragOver] = useState<string | null>(null)

  const params = { inicio, tipo, zona_id: zona, cliente_id: cliente, supervisor_id: supervisor, colaborador_id: colaborador }
  const q = useQuery({ queryKey: ['planeamento', params], queryFn: () => api<Plan>('/planeamento', { params }) })
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<Cliente[]>('/clientes') })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })

  const refresh = () => qc.invalidateQueries({ queryKey: ['planeamento'] })
  const erro = (e: unknown) => toast(e instanceof Error ? e.message : 'Erro', 'err')

  const mSubst = useMutation({
    mutationFn: (v: { id: number; colaborador_id: number | null; motivo?: string }) =>
      api(`/ocorrencias/${v.id}/colaborador`, { method: 'PUT', body: { colaborador_id: v.colaborador_id, motivo: v.motivo } }),
    onSuccess: () => { refresh(); toast('Turno atualizado') }, onError: erro,
  })
  const mMover = useMutation({
    mutationFn: (v: { id: number; data: string }) => api(`/ocorrencias/${v.id}/data`, { method: 'PUT', body: { data: v.data } }),
    onSuccess: () => { refresh(); toast('Turno movido') }, onError: erro,
  })
  const mAfetar = useMutation({
    mutationFn: (v: { linha: number; colaborador_id: number; desde: string }) =>
      api(`/linhas/${v.linha}/afetacao`, { method: 'POST', body: { colaborador_id: v.colaborador_id, desde: v.desde } }),
    onSuccess: () => { refresh(); qc.invalidateQueries({ queryKey: ['contrato'] }); toast('Colaborador afeto até ao fim do contrato') }, onError: erro,
  })

  const data = q.data
  const porCelula = useMemo(() => {
    const m = new Map<string, Ocorrencia[]>()
    data?.ocorrencias.forEach((o) => { const k = `${o.colaborador_id}|${o.data}`; m.set(k, [...(m.get(k) ?? []), o]) })
    data?.por_atribuir.forEach((o) => { const k = `0|${o.data}`; m.set(k, [...(m.get(k) ?? []), o]) })
    return m
  }, [data])
  const todas = useMemo(() => [...(data?.ocorrencias ?? []), ...(data?.por_atribuir ?? [])], [data])
  const selecionada = todas.find((o) => o.id === sel) ?? null
  const nomeColab = (id: number | null) => data?.colaboradores.find((c) => c.id === id)?.nome ?? '—'
  const hoje = iso(new Date())

  function onDrop(colaboradorId: number, dia: string, e: React.DragEvent) {
    e.preventDefault()
    setDragOver(null)
    const id = Number(e.dataTransfer.getData('text/plain'))
    const oc = todas.find((o) => o.id === id)
    if (!oc) return
    if (colaboradorId === 0) {
      if (oc.colaborador_id) mSubst.mutate({ id: oc.id, colaborador_id: null })
      return
    }
    if (oc.data !== dia && oc.colaborador_id === colaboradorId) { mMover.mutate({ id: oc.id, data: dia }); return }
    if (oc.colaborador_id === colaboradorId) return
    setDrop({ oc, colaboradorId, data: dia })
  }

  const aus = (c: LinhaColaborador, dia: string) => c.ausencias.find((a) => a.inicio <= dia && dia <= a.fim)

  return (
    <>
      <PageHeader crumb="Operação" title="Planeamento"
        sub={data ? `Semana ${semanaISO(data.inicio)} · ${intervaloSemana(data.inicio, data.fim)}` : ' '}>
        <div className="flex gap-1.5">
          <IconButton icon="cl" label="Semana anterior" onClick={() => setInicio(iso(addDays(parseISO(inicio), -7)))} />
          <Button onClick={() => setInicio(iso(segunda(new Date())))}>Hoje</Button>
          <IconButton icon="cr" label="Semana seguinte" onClick={() => setInicio(iso(addDays(parseISO(inicio), 7)))} />
        </div>
        <Seg label="Área" value={tipo} onChange={setTipo} options={[{ value: '', label: 'Todas' }, { value: 'REP', label: 'Reposição' }, { value: 'PRO', label: 'Promoções' }]} />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        {colaborador && (
          <button type="button" onClick={limparColaborador} className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-petrol-600 bg-[#E9F4F2] text-[13px] text-petrol-700">
            Colaborador: <b className="font-medium">{data?.colaboradores.find((c) => String(c.id) === colaborador)?.nome ?? '…'}</b><Icon name="x" size={14} />
          </button>
        )}
        <FiltroSelect label={colaborador ? 'Por atribuir na zona' : 'Zona'} value={zona} onChange={setZona} options={zonas.data} />
        <FiltroSelect label="Cliente" value={cliente} onChange={setCliente} options={clientes.data} />
        <FiltroSelect label="Supervisor" value={supervisor} onChange={setSupervisor} options={sups.data} />
        {(zona || cliente || supervisor || colaborador) && <Button variant="ghost" size="sm" onClick={() => { setZona(''); setCliente(''); setSupervisor(''); if (colaborador) limparColaborador() }}>Limpar filtros</Button>}
        <span className="flex-1" />
        {data && <>
          <Badge>{data.resumo.total} turnos · {horas(data.resumo.horas)}</Badge>
          <Badge tone={data.resumo.por_atribuir ? 'err' : 'ok'} dot>{data.resumo.por_atribuir} por atribuir</Badge>
          <Badge tone={data.resumo.ausencias ? 'warn' : 'neu'} dot>{data.resumo.ausencias} {data.resumo.ausencias === 1 ? "ausência" : "ausências"}</Badge>
          <Badge tone={data.resumo.conflitos ? 'err' : 'neu'} dot>{data.resumo.conflitos} conflitos</Badge>
          {!!data.resumo.documentacao && <Link to="/documentacao" title="Turnos com documentação obrigatória em falta ou expirada"><Badge tone="warn" dot>{data.resumo.documentacao} com documentação pendente</Badge></Link>}
        </>}
      </div>

      {q.isLoading ? <Card><Loading /></Card> : q.error ? <ErrorBox error={q.error} /> : data && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <div role="grid" aria-label="Escala semanal" className="grid min-w-[1040px]" style={{ gridTemplateColumns: '220px repeat(7, minmax(116px, 1fr))' }}>
              <div className="px-2.5 py-2 text-xs text-ink-60 border-b border-line bg-[#FAFBF9] border-r border-line flex items-end">Colaborador</div>
              {data.dias.map((d, i) => {
                const n = [...(porCelula.entries())].filter(([k]) => k.endsWith('|' + d)).reduce((s, [, v]) => s + v.length, 0)
                return (
                  <div key={d} className={`px-2.5 py-2 text-xs border-b border-line border-r border-[#F1F3F0] ${d === hoje ? 'bg-petrol-50 text-petrol-700' : 'bg-[#FAFBF9] text-ink-60'}`}>
                    <b className={`block text-[13.5px] font-semibold ${d === hoje ? 'text-petrol-700' : 'text-ink'}`}>{diaSemana(d)} {parseISO(d).getDate()}</b>
                    {n} turnos{d === hoje ? ' · hoje' : ''}{i >= 5 ? '' : ''}
                  </div>
                )
              })}

              {/* linha "Por atribuir" */}
              <div className="px-3 py-2.5 border-b border-line-soft border-r border-line bg-[#FBF8F1] flex gap-2.5 items-start">
                <span className="grid place-items-center w-7 h-7 rounded-full bg-err-bg text-err-fg"><Icon name="alert" size={14} /></span>
                <div><div className="font-medium text-[13px]">Por atribuir</div><div className="text-xs text-ink-60">Arraste para um colaborador</div></div>
              </div>
              {data.dias.map((d) => (
                <Celula key={d} k={`0|${d}`} dragOver={dragOver} setDragOver={setDragOver} onDrop={(e) => onDrop(0, d, e)} className="bg-[#FBF8F1]">
                  {(porCelula.get(`0|${d}`) ?? []).map((o) => <Turno key={o.id} o={o} sel={sel === o.id} onClick={() => setSel(o.id)} />)}
                </Celula>
              ))}

              {data.colaboradores.map((c, idx) => (
                <ColabRow key={c.id} c={c} idx={idx}>
                  {data.dias.map((d) => {
                    const a = aus(c, d)
                    return (
                      <Celula key={d} k={`${c.id}|${d}`} dragOver={dragOver} setDragOver={setDragOver} onDrop={(e) => onDrop(c.id, d, e)}
                        className={`${d === hoje ? 'bg-[#F5FAF9]' : parseISO(d).getDay() % 6 === 0 ? 'bg-[#FAFAF8]' : ''}`}>
                        {a && <div className="rounded-md px-2 py-1 text-xs text-[#6B4000] bg-[repeating-linear-gradient(135deg,#FCEFD7_0_7px,#FAF3E3_7px_14px)] flex items-center gap-1.5">
                          <Icon name="sun" size={13} />{a.tipo === 'ferias' ? 'Férias' : 'Ausente'}</div>}
                        {(porCelula.get(`${c.id}|${d}`) ?? []).map((o) => <Turno key={o.id} o={o} sel={sel === o.id} onClick={() => setSel(o.id)} />)}
                      </Celula>
                    )
                  })}
                </ColabRow>
              ))}
            </div>
            {data.colaboradores.length === 0 && data.por_atribuir.length === 0 && (
              <div className="px-6 py-10 text-center text-ink-60 text-sm">Sem turnos nesta semana com os filtros escolhidos.</div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-4 px-3.5 py-2.5 border-t border-line bg-[#FAFBF9] text-[12.5px] text-ink-60">
            {(['REP', 'PRO'] as const).map((t) => <span key={t} className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-sm ${AREA[t].sq}`} />{AREA[t].label}</span>)}
            <span className="flex items-center gap-1.5"><Icon name="swap" size={13} />Substituição</span>
            <span className="flex items-center gap-1.5"><Icon name="alert" size={13} className="text-err" />Alerta</span>
            <span className="flex items-center gap-1.5"><Icon name="cal" size={13} />Reagendado por feriado</span>
            <span className="flex-1" />
            <span>Arraste um turno para outro colaborador ou dia</span>
          </div>
        </Card>
      )}

      {selecionada && (
        <Card className="flex flex-wrap items-center gap-3.5 px-4 py-3" >
          <div className="flex-[1_1_360px] min-w-0" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-60">
              Turno selecionado <AreaBadge tipo={selecionada.tipo} />
              {selecionada.substituicao && <Badge tone="info">Substituição</Badge>}
              {selecionada.alertas.map((a) => <Badge key={a} tone={a === 'documentacao' ? 'warn' : 'err'} dot>{ALERTA[a] ?? a}</Badge>)}
            </div>
            <div className="font-semibold text-[14.5px] mt-0.5">
              {diaSemana(selecionada.data)} {diaMes(selecionada.data)}{selecionada.hora_inicio ? ` · ${selecionada.hora_inicio}` : ''} · {horas(selecionada.horas)} · {selecionada.loja}
            </div>
            <div className="text-[12.5px] text-ink-60">
              {selecionada.cliente}{selecionada.mecanica ? ` · ${selecionada.mecanica}` : ''} · <Link className="text-petrol-600 hover:underline" to={`/contratos/${selecionada.contrato_id}`}>{selecionada.contrato_numero}</Link>
              {' · '}{selecionada.colaborador_id ? nomeColab(selecionada.colaborador_id) : 'sem colaborador'}
              {selecionada.substituicao && ` (substitui ${nomeColab(selecionada.colaborador_previsto_id)})`}
              {selecionada.reagendada_feriado && ` · reagendado de ${diaMes(selecionada.data_original)} (feriado)`}
            </div>
            {!!selecionada.documentacao?.length && (
              <div className="text-[12.5px] text-warn-fg flex gap-1.5 mt-1"><Icon name="shield" size={14} className="mt-0.5 flex-none" />
                <span>{selecionada.documentacao.join(' · ')} · <Link to={`/colaboradores?id=${selecionada.colaborador_id}`} className="underline">ver documentos</Link></span></div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button icon="swap" onClick={() => setSubst(selecionada)}>{selecionada.colaborador_id ? 'Substituir' : 'Atribuir'}</Button>
            {selecionada.substituicao && <Button icon="hist" onClick={() => mSubst.mutate({ id: selecionada.id, colaborador_id: null })}>Repor colaborador afeto</Button>}
            <Button variant="ghost" onClick={() => setSel(null)}>Fechar</Button>
          </div>
        </Card>
      )}

      {drop && (
        <DropDialog drop={drop} nome={nomeColab(drop.colaboradorId)} onClose={() => setDrop(null)}
          onSoEste={() => {
            if (drop.data !== drop.oc.data) mMover.mutate({ id: drop.oc.id, data: drop.data })
            mSubst.mutate({ id: drop.oc.id, colaborador_id: drop.colaboradorId, motivo: 'Alteração no planeamento' }); setDrop(null)
          }}
          onAfetar={() => { mAfetar.mutate({ linha: drop.oc.linha_id, colaborador_id: drop.colaboradorId, desde: drop.oc.data }); setDrop(null) }} />
      )}
      {subst && <SubstDialog oc={subst} onClose={() => setSubst(null)}
        onEscolher={(cid, persistente) => {
          if (persistente) mAfetar.mutate({ linha: subst.linha_id, colaborador_id: cid, desde: subst.data })
          else mSubst.mutate({ id: subst.id, colaborador_id: cid, motivo: 'Substituição' })
          setSubst(null)
        }} />}
    </>
  )
}

function FiltroSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options?: IdNome[] }) {
  return (
    <label className={`inline-flex items-center gap-1.5 h-8 pl-2.5 pr-1 rounded-md border text-[13px] ${value ? 'border-petrol-600 bg-[#E9F4F2] text-petrol-700' : 'border-line-strong bg-white text-ink-80'}`}>
      {label}:
      <select value={value} onChange={(e) => onChange(e.target.value)} className="bg-transparent font-medium text-ink outline-none pr-1">
        <option value="">Todos</option>
        {options?.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
      </select>
    </label>
  )
}

function ColabRow({ c, idx, children }: { c: LinhaColaborador; idx: number; children: React.ReactNode }) {
  const pct = c.limite_semana ? (c.horas_semana / c.limite_semana) * 100 : 0
  return (
    <>
      <div className="px-3 py-2.5 border-b border-line-soft border-r border-line flex gap-2.5 items-start min-w-0">
        <Avatar nome={c.nome} tone={idx} />
        <div className="min-w-0">
          <div className="font-medium text-[13px] leading-tight">{c.nome}</div>
          <div className="text-xs text-ink-60">{VINCULO[c.vinculo].label}{c.funcao ? ` · ${c.funcao}` : ''}</div>
          <div className="text-xs text-ink-60 num">{horas(c.horas_semana)}{c.limite_semana ? ` / ${c.limite_semana} h` : ' · prestador'}</div>
          {c.limite_semana && <div className="w-24 mt-1"><Bar2 pct={pct} /></div>}
          {c.alertas.map((a) => <div key={a} className="text-xs text-err-fg mt-1 flex gap-1"><Icon name="alert" size={12} className="mt-0.5" />{a}</div>)}
        </div>
      </div>
      {children}
    </>
  )
}

function Bar2({ pct }: { pct: number }) {
  return <div className="h-1 rounded bg-[#E6E9E5] overflow-hidden"><div className={`h-full ${pct > 100 ? 'bg-err' : pct >= 95 ? 'bg-warn' : 'bg-petrol-600'}`} style={{ width: `${Math.min(100, pct)}%` }} /></div>
}

function Celula({ k, children, className = '', onDrop, dragOver, setDragOver }: {
  k: string; children: React.ReactNode; className?: string; onDrop: (e: React.DragEvent) => void
  dragOver: string | null; setDragOver: (k: string | null) => void
}) {
  return (
    <div onDragOver={(e) => { e.preventDefault(); if (dragOver !== k) setDragOver(k) }} onDragLeave={() => setDragOver(null)} onDrop={onDrop}
      className={`p-[5px] border-b border-line-soft border-r border-[#F1F3F0] flex flex-col gap-[5px] min-h-[78px] min-w-0 ${dragOver === k ? 'outline outline-2 -outline-offset-2 outline-petrol-600 bg-petrol-50' : ''} ${className}`}>
      {children}
    </div>
  )
}

function Turno({ o, sel, onClick }: { o: Ocorrencia; sel: boolean; onClick: () => void }) {
  const a = AREA[o.tipo]
  const sem = o.colaborador_id === null
  const alerta = o.alertas.some((x) => x !== 'sem_colaborador')
  return (
    <button type="button" draggable onDragStart={(e) => { e.dataTransfer.setData('text/plain', String(o.id)); e.dataTransfer.effectAllowed = 'move' }}
      onClick={onClick} aria-label={`${o.loja}, ${o.cliente}, ${horas(o.horas)}`}
      className={`text-left w-full rounded-lg px-2 py-1.5 text-xs leading-snug cursor-grab active:cursor-grabbing border
        ${sem ? 'bg-white border-dashed border-[#A3ADA7] text-ink-80' : `${a.cls} border-transparent`}
        ${alerta ? '!border-2 !border-err' : ''} ${sel ? 'ring-2 ring-ink' : ''} hover:brightness-[.97]`}>
      <span className="flex items-center gap-1.5 font-semibold">
        <span className={`w-2 h-2 rounded-sm ${a.sq}`} />{o.hora_inicio ?? ''}{o.hora_inicio ? ' · ' : ''}{horas(o.horas)}
        <span className="ml-auto flex gap-0.5">
          {o.substituicao && <Icon name="swap" size={12} />}
          {o.reagendada_feriado && <Icon name="cal" size={12} />}
          {alerta && <Icon name="alert" size={12} className="text-err" />}
        </span>
      </span>
      <span className="block truncate">{o.loja}</span>
      <span className="block truncate opacity-90">{o.cliente}</span>
    </button>
  )
}

function DropDialog({ drop, nome, onClose, onSoEste, onAfetar }: { drop: Drop; nome: string; onClose: () => void; onSoEste: () => void; onAfetar: () => void }) {
  const titular = drop.oc.colaborador_id !== null
  return (
    <Modal title={`${titular ? 'Mudar' : 'Atribuir'} turno de ${drop.oc.loja}`} onClose={onClose} width={520}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button onClick={onSoEste}>Só este turno</Button>
        <Button variant="primary" onClick={onAfetar} disabled={drop.data !== drop.oc.data}>Afetar até ao fim</Button></>}>
      <p className="text-[13.5px]">
        <b>{nome}</b> vai ficar com o turno de <b>{diaSemana(drop.data)} {diaMes(drop.data)}</b> ({horas(drop.oc.horas)}, {drop.oc.cliente}).
      </p>
      <ul className="mt-3 text-[13px] text-ink-80 flex flex-col gap-1.5 list-disc pl-5">
        <li><b>Afetar até ao fim</b>: {nome} passa a fazer esta loja em todos os turnos a partir desta data, até ao fim do contrato. É a opção habitual.</li>
        <li><b>Só este turno</b>: substituição pontual; o colaborador afeto mantém-se nos restantes dias.</li>
      </ul>
      {drop.data !== drop.oc.data && <p className="mt-3 text-xs text-ink-60">Mudou também o dia: só é possível como alteração deste turno.</p>}
    </Modal>
  )
}

function SubstDialog({ oc, onClose, onEscolher }: { oc: Ocorrencia; onClose: () => void; onEscolher: (cid: number, persistente: boolean) => void }) {
  const q = useQuery({ queryKey: ['candidatos', oc.id], queryFn: () => api<Candidato[]>(`/ocorrencias/${oc.id}/candidatos`) })
  const [persistente, setPersistente] = useState(!oc.colaborador_id)
  return (
    <Modal title={`${oc.colaborador_id ? 'Substituir' : 'Atribuir'} · ${oc.loja}, ${diaSemana(oc.data)} ${diaMes(oc.data)}`} onClose={onClose} width={620}>
      <label className="flex items-center gap-2 text-[13px] mb-3">
        <input type="checkbox" checked={persistente} onChange={(e) => setPersistente(e.target.checked)} className="w-4 h-4 accent-petrol-600" />
        Afetar à loja a partir desta data até ao fim do contrato (em vez de só este turno)
      </label>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : (
        <ul className="flex flex-col divide-y divide-line-soft">
          {q.data?.map((c, i) => (
            <li key={c.colaborador_id} className="flex items-start gap-3 py-2.5">
              <Avatar nome={c.nome} tone={i} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-[13.5px]">{c.nome} <span className="text-xs text-ink-60 font-normal">· {VINCULO[c.vinculo].label} · {horas(c.horas_semana)} nesta semana</span></div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {c.motivos.map((m) => <Badge key={m} tone="ok">{m}</Badge>)}
                  {c.alertas.map((m) => <Badge key={m} tone="warn">{m}</Badge>)}
                </div>
              </div>
              <Button size="sm" variant={i === 0 && !c.alertas.length ? 'primary' : 'secondary'} onClick={() => onEscolher(c.colaborador_id, persistente)}>Escolher</Button>
            </li>
          ))}
          {q.data?.length === 0 && <li className="py-6 text-center text-ink-60 text-sm">Sem colaboradores elegíveis.</li>}
        </ul>
      )}
      <p className="text-xs text-ink-60 mt-3">A sugestão ordena por disponibilidade, zona e carga semanal. Pode escolher qualquer colaborador; os alertas não bloqueiam.</p>
    </Modal>
  )
}
