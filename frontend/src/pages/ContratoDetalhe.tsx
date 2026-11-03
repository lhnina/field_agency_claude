import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LojaPicker } from '../components/LojaPicker'
import { ColaboradorPicker } from '../components/ColaboradorPicker'
import { AreaBadge, Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { api } from '../lib/api'
import { ESTADO_CONTRATO, dataCurta, eur, horas, iso, num } from '../lib/format'
import { DIAS } from '../lib/types'
import type { Contrato, Linha } from '../lib/types'
import { NovoContrato } from './Contratos'

const DIA_LABEL = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

export default function ContratoDetalhe() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['contrato', Number(id)], queryFn: () => api<Contrato>(`/contratos/${id}`) })
  const [linhaEdit, setLinhaEdit] = useState<Linha | 'nova' | null>(null)
  const [afetar, setAfetar] = useState<Linha | null>(null)
  const [editar, setEditar] = useState(false)
  const [verTerminadas, setVerTerminadas] = useState(false)
  const set = (c: Contrato) => { qc.setQueryData(['contrato', c.id], c); qc.invalidateQueries({ queryKey: ['contratos'] }); qc.invalidateQueries({ queryKey: ['planeamento'] }) }
  const estado = useMutation({
    mutationFn: (e: string) => api<Contrato>(`/contratos/${id}/estado`, { method: 'POST', body: { estado: e } }),
    onSuccess: (c) => { set(c); toast(c.estado === 'ativo' ? 'Contrato ativo: ocorrências geradas no planeamento' : 'Estado atualizado') },
    onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })

  if (q.isLoading) return <Card><Loading /></Card>
  if (q.error || !q.data) return <ErrorBox error={q.error} />
  const c = q.data
  const est = ESTADO_CONTRATO[c.estado]
  const hojeIso = iso(new Date())
  const terminou = (ln: Linha) => ln.fim !== null && ln.fim < hojeIso
  const terminadas = c.linhas.filter(terminou).length
  const linhasVisiveis = verTerminadas ? c.linhas : c.linhas.filter((ln) => !terminou(ln))

  return (
    <>
      <div className="flex flex-wrap items-start gap-3.5">
        <div className="flex-1 min-w-[300px]">
          <div className="flex items-center gap-1.5 text-[12.5px] text-ink-60 mb-1">
            <Link to="/contratos" className="text-petrol-600 hover:underline">Contratos</Link><Icon name="cr" size={13} /><span className="font-mono">{c.numero}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-[-0.02em]">{c.cliente_nome}{c.evento ? ` · ${c.evento}` : ''}</h1>
            <AreaBadge tipo={c.tipo} /><Badge tone={est.tone} dot>{est.label}</Badge><Badge>Versão {c.versao}</Badge>
          </div>
          <div className="text-[12.5px] text-ink-60 mt-1.5">
            Vigência {dataCurta(c.inicio)} – {c.fim ? dataCurta(c.fim) : 'sem termo'} · Faturação: horas contratadas (h/semana × 52 ÷ 12){c.marca_nome ? ` · Marca ${c.marca_nome}` : ''}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon="edit" onClick={() => setEditar(true)}>Editar</Button>
          {c.estado === 'proposta' && <Button variant="primary" icon="check" loading={estado.isPending} onClick={() => estado.mutate('ativo')}>Ativar contrato</Button>}
          {c.estado === 'ativo' && <Button onClick={() => estado.mutate('suspenso')}>Suspender</Button>}
          {c.estado === 'suspenso' && <Button variant="primary" onClick={() => estado.mutate('ativo')}>Reativar</Button>}
          {c.estado === 'ativo' && <Button variant="primary" icon="cal" onClick={() => nav('/planeamento')}>Ver no planeamento</Button>}
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="grid grid-cols-2 md:grid-cols-4 border-b border-line-soft">
          {[
            ['Valor mensal', eur(c.valor_mensal), `${c.n_linhas} lojas`],
            ['Horas contratadas', `${horas(c.horas_mes)}/mês`, `${horas(c.horas_semana)} por semana`],
            ['Linhas por atribuir', String(c.linhas_por_atribuir), c.linhas_por_atribuir ? 'sem colaborador afeto' : 'todas atribuídas'],
            ['Preço médio/hora', Number(c.horas_semana) ? eur(Number(c.valor_mensal) / Number(c.horas_mes)) : '—', 'ponderado pelas horas'],
          ].map(([l, v, s], i) => (
            <div key={l} className={`px-[18px] py-3.5 ${i < 3 ? 'md:border-r border-line-soft' : ''}`}>
              <div className="text-xs text-ink-60">{l}</div>
              <div className={`text-xl font-semibold tracking-[-0.02em] mt-0.5 num ${l === 'Linhas por atribuir' && c.linhas_por_atribuir ? 'text-err-fg' : ''}`}>{v}</div>
              <div className="text-xs text-ink-60 mt-0.5">{s}</div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 bg-[#FAFBF9] border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Linhas por loja</h3>
          <span className="text-[12.5px] text-ink-60">as horas de cada dia são distribuídas pelo colaborador</span>
          <span className="flex-1" />
          {terminadas > 0 && (
            <label className="flex items-center gap-2 text-[13px] text-ink-80 whitespace-nowrap mr-2">
              <input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={verTerminadas} onChange={(e) => setVerTerminadas(e.target.checked)} />
              Mostrar terminadas ({terminadas})
            </label>
          )}
          <Button size="sm" icon="plus" onClick={() => setLinhaEdit('nova')}>Adicionar loja</Button>
        </div>
        {c.linhas.length === 0 ? <Empty title="Sem lojas neste contrato">Adicione as lojas com as horas por dia da semana e o preço por hora.</Empty>
          : linhasVisiveis.length === 0 ? <Empty title="Todas as lojas deste contrato já terminaram">Marque «Mostrar terminadas» para as ver.</Empty> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr>
                <th>Loja</th>{c.tipo === 'PRO' && <th>Mecânica</th>}{DIA_LABEL.map((d) => <th key={d} className="!text-center !px-1 w-10">{d}</th>)}
                <th className="text-right">Total/sem</th><th className="text-right">Preço/h</th><th className="text-right">Valor mensal</th><th>Colaborador afeto</th><th>Vigência</th><th>Observações</th><th />
              </tr></thead>
              <tbody>
                {linhasVisiveis.map((ln, i) => {
                  const inativa = terminou(ln)
                  return (
                    <tr key={ln.id} className={inativa ? '[&>td]:!bg-[#EEF0EC] text-ink-60' : ''} title={inativa ? `Terminada a ${dataCurta(ln.fim)}` : undefined}>
                      <td>
                        <button type="button" onClick={() => setLinhaEdit(ln)} className="font-medium text-left hover:underline hover:text-petrol-600">{ln.loja_nome}</button>
                        <div className="text-xs text-ink-60">{[ln.loja_insignia, ln.loja_zona].filter(Boolean).join(' · ')}</div>
                      </td>
                      {c.tipo === 'PRO' && (
                        <td className="whitespace-nowrap">
                          <div>{ln.mecanica ?? <span className="text-ink-60">—</span>}</div>
                          <div className="text-xs text-ink-60 num">{ln.hora_inicio ? `início ${ln.hora_inicio.slice(0, 5)}` : 'sem hora de início'}</div>
                        </td>
                      )}
                      {DIAS.map((d) => { const v = Number(ln[`h_${d}`]); return <td key={d} className={`!text-center !px-1 num ${v ? '' : 'text-[#B6BDB8]'}`}>{v ? num(v) : '–'}</td> })}
                      <td className="text-right num font-medium">{horas(ln.horas_semana)}</td>
                      <td className="text-right num">{eur(ln.preco_hora)}</td>
                      <td className="text-right num">{eur(ln.valor_mensal)}</td>
                      <td>
                        {ln.afetacao_atual ? (
                          <button type="button" onClick={() => setAfetar(ln)} className="flex items-center gap-2 hover:underline text-left">
                            <Avatar nome={ln.afetacao_atual.colaborador_nome} tone={i} />
                            <span>{ln.afetacao_atual.colaborador_nome}<span className="block text-xs text-ink-60">desde {dataCurta(ln.afetacao_atual.desde)}{ln.afetacao_atual.ate ? ` até ${dataCurta(ln.afetacao_atual.ate)}` : ''}</span></span>
                          </button>
                        ) : inativa ? <span className="text-ink-60">—</span>
                          : <Button size="sm" variant="secondary" onClick={() => setAfetar(ln)} className="!text-err-fg">Por atribuir · Afetar</Button>}
                      </td>
                      <td className="text-xs text-ink-60 num whitespace-nowrap">{dataCurta(ln.inicio)}<br />{ln.fim ? dataCurta(ln.fim) : 'sem termo'}
                        {inativa && <div className="mt-0.5"><Badge>Terminada</Badge></div>}</td>
                      <td className="text-xs text-ink-60 max-w-[200px]"><div className="line-clamp-2" title={ln.observacoes ?? undefined}>{ln.observacoes || '—'}</div></td>
                      <td className="text-right"><button type="button" aria-label={`Editar ${ln.loja_nome}`} onClick={() => setLinhaEdit(ln)} className="text-ink-60 hover:text-ink p-1"><Icon name="edit" size={16} /></button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-4 px-4 py-3 border-t border-line text-[12.5px] text-ink-60">
          {c.estado === 'proposta' && <span className="flex items-center gap-1.5 text-warn-fg"><Icon name="alert" size={14} />Ative o contrato para gerar as ocorrências no planeamento.</span>}
          <span className="flex-1" />
          <span className="num">Total: <b className="text-ink font-semibold">{horas(c.horas_semana)}/semana · {horas(c.horas_mes)}/mês · {eur(c.valor_mensal)}/mês</b></span>
        </div>
      </Card>

      {linhaEdit && <LinhaDialog contrato={c} linha={linhaEdit === 'nova' ? null : linhaEdit} onClose={() => setLinhaEdit(null)} onSaved={(x) => { set(x); setLinhaEdit(null) }} />}
      {afetar && <AfetarDialog linha={afetar} onClose={() => setAfetar(null)} onSaved={(x) => { set(x); setAfetar(null) }} />}
      {editar && <NovoContrato inicial={c} onClose={() => setEditar(false)} onCriado={() => setEditar(false)} />}
    </>
  )
}

function LinhaDialog({ contrato, linha, onClose, onSaved }: { contrato: Contrato; linha: Linha | null; onClose: () => void; onSaved: (c: Contrato) => void }) {
  const toast = useToast()
  const pro = contrato.tipo === 'PRO'
  const [f, setF] = useState(() => ({
    loja: linha ? { id: linha.loja_id, nome: linha.loja_nome } : null as { id: number; nome: string } | null, inicio: linha?.inicio ?? (contrato.inicio > iso(new Date()) ? contrato.inicio : iso(new Date())),
    fim: linha?.fim ?? contrato.fim ?? '', preco_hora: linha?.preco_hora ?? '18.00', hora_inicio: linha?.hora_inicio ?? '',
    mecanica: linha?.mecanica ?? '', custo_hora_especial: linha?.custo_hora_especial ?? '', observacoes: linha?.observacoes ?? '',
    h: DIAS.map((d) => (linha ? String(Number(linha[`h_${d}`]) || '') : '')),
  }))
  const erroInicio = !f.inicio ? 'Indique a data de início'
    : f.inicio < contrato.inicio ? `Não pode ser antes do início do contrato (${dataCurta(contrato.inicio)})`
    : contrato.fim && f.inicio > contrato.fim ? `Não pode ser depois do fim do contrato (${dataCurta(contrato.fim)})` : null
  const erroFim = !f.fim ? null
    : f.inicio && f.fim < f.inicio ? 'O fim não pode ser antes do início'
    : contrato.fim && f.fim > contrato.fim ? `Não pode ser depois do fim do contrato (${dataCurta(contrato.fim)})` : null
  const total = f.h.reduce((s, v) => s + (Number(v.replace(',', '.')) || 0), 0)
  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        loja_id: f.loja!.id, inicio: f.inicio, fim: f.fim || null, preco_hora: Number(String(f.preco_hora).replace(',', '.')),
        hora_inicio: f.hora_inicio || null, mecanica: f.mecanica || null, observacoes: f.observacoes || null,
        custo_hora_especial: f.custo_hora_especial ? Number(String(f.custo_hora_especial).replace(',', '.')) : null,
      }
      DIAS.forEach((d, i) => { body[`h_${d}`] = Number(f.h[i].replace(',', '.')) || 0 })
      return api<Contrato>(linha ? `/linhas/${linha.id}` : `/contratos/${contrato.id}/linhas`, { method: linha ? 'PUT' : 'POST', body })
    },
    onSuccess: (c) => { toast(linha ? 'Linha atualizada; ocorrências futuras recalculadas' : 'Loja adicionada ao contrato'); onSaved(c) },
  })
  return (
    <Modal title={linha ? `Editar ${linha.loja_nome}` : 'Adicionar loja ao contrato'} onClose={onClose} width={640}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.loja || total === 0 || !!erroInicio || !!erroFim} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Loja" className="col-span-2">{(id) => (
          <LojaPicker id={id} value={f.loja} usadas={new Set(contrato.linhas.map((l) => l.loja_id))}
            onChange={(l) => setF({ ...f, loja: l ? { id: l.id, nome: l.nome } : null })} />)}</Field>
        <div className="col-span-2">
          <div className="lbl mb-1.5">Horas por dia da semana</div>
          <div className="grid grid-cols-7 gap-2">
            {DIA_LABEL.map((d, i) => (
              <label key={d} className="flex flex-col gap-1 text-xs text-ink-60 text-center">{d}
                <input inputMode="decimal" className="inp text-center num" value={f.h[i]} placeholder="0"
                  onChange={(e) => { const h = [...f.h]; h[i] = e.target.value; setF({ ...f, h }) }} />
              </label>
            ))}
          </div>
          <div className="text-xs text-ink-60 mt-1.5 num">Total {num(total)} h/semana · {num(total * 52 / 12)} h/mês · {eur(total * 52 / 12 * (Number(String(f.preco_hora).replace(',', '.')) || 0))}/mês</div>
        </div>
        <Field label="Preço por hora (€)">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.preco_hora} onChange={(e) => setF({ ...f, preco_hora: e.target.value })} />}</Field>
        <Field label="Custo Fixo (€/h)" hint="Vazio = custo do colaborador">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.custo_hora_especial} onChange={(e) => setF({ ...f, custo_hora_especial: e.target.value })} />}</Field>
        <Field label="Início" error={erroInicio}>{(id) => <DataInput id={id} invalid={!!erroInicio} value={f.inicio} min={contrato.inicio} max={contrato.fim ?? undefined} onChange={(v) => setF({ ...f, inicio: v })} />}</Field>
        <Field label="Fim" error={erroFim} hint={erroFim ? undefined : contrato.fim ? `Vazio = até ao fim do contrato (${dataCurta(contrato.fim)})` : 'Vazio = sem termo, como o contrato'}>{(id) => <DataInput id={id} limpar invalid={!!erroFim} value={f.fim} min={f.inicio || contrato.inicio} max={contrato.fim ?? undefined} onChange={(v) => setF({ ...f, fim: v })} />}</Field>
        <p className="col-span-2 -mt-1.5 text-xs text-ink-60">Vigência do contrato: {dataCurta(contrato.inicio)} a {contrato.fim ? dataCurta(contrato.fim) : 'sem termo'}. As datas da loja têm de ficar dentro desta vigência.</p>
        {pro && <>
          <Field label="Hora de início">{(id) => <input id={id} type="time" className="inp" value={f.hora_inicio} onChange={(e) => setF({ ...f, hora_inicio: e.target.value })} />}</Field>
          <Field label="Mecânica">{(id) => (
            <select id={id} className="inp" value={f.mecanica} onChange={(e) => setF({ ...f, mecanica: e.target.value })}>
              <option value="">—</option>{['Degustação', 'Amostras', 'Inquérito', 'Promoção', 'Ativação'].map((x) => <option key={x}>{x}</option>)}
            </select>)}</Field>
        </>}
        <Field label="Observações" className="col-span-2">{(id) => <textarea id={id} rows={2} className="inp !h-auto py-2 resize-y" placeholder="Notas sobre o serviço nesta loja (acesso, contacto, regras da loja…)" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      {linha && <p className="text-xs text-ink-60 mt-3">Ao guardar, as ocorrências futuras desta loja que ainda não foram executadas são recalculadas.</p>}
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function AfetarDialog({ linha, onClose, onSaved }: { linha: Linha; onClose: () => void; onSaved: (c: Contrato) => void }) {
  const toast = useToast()
  const [colab, setColab] = useState<{ id: number; nome: string } | null>(linha.afetacao_atual ? { id: linha.afetacao_atual.colaborador_id, nome: linha.afetacao_atual.colaborador_nome } : null)
  const [desde, setDesde] = useState(linha.inicio > iso(new Date()) ? linha.inicio : iso(new Date()))
  const [ate, setAte] = useState('')
  const m = useMutation({
    mutationFn: () => api<Contrato>(`/linhas/${linha.id}/afetacao`, { method: 'POST', body: { colaborador_id: colab!.id, desde, ate: ate || null } }),
    onSuccess: (c) => { toast('Afetação guardada; planeamento atualizado'); onSaved(c) },
  })
  const remover = useMutation({
    mutationFn: () => api<Contrato>(`/linhas/${linha.id}/afetacao`, { method: 'DELETE', params: { desde } }),
    onSuccess: (c) => { toast('Afetação terminada; turnos ficam por atribuir', 'warn'); onSaved(c) },
  })
  return (
    <Modal title={`Afetação · ${linha.loja_nome}`} onClose={onClose}
      footer={<>
        {linha.afetacao_atual && <Button variant="danger" loading={remover.isPending} onClick={() => remover.mutate()} className="mr-auto">Terminar afetação</Button>}
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="primary" loading={m.isPending} disabled={!colab} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Colaborador" className="col-span-2">{(id) => (
          <ColaboradorPicker id={id} value={colab} zonaPreferida={linha.loja_zona}
            onChange={(c) => setColab(c ? { id: c.id, nome: c.nome } : null)} />)}</Field>
        <Field label="A partir de">{(id) => <DataInput id={id} value={desde} min={linha.inicio} max={linha.fim ?? undefined} onChange={setDesde} />}</Field>
        <Field label="Até" hint="Vazio = até ao fim do contrato">{(id) => <DataInput id={id} limpar value={ate} min={desde || undefined} max={linha.fim ?? undefined} onChange={setAte} />}</Field>
      </div>
      {linha.afetacoes.length > 0 && (
        <div className="mt-4">
          <div className="lbl mb-1.5">Histórico</div>
          <ul className="text-[13px] flex flex-col gap-1">
            {linha.afetacoes.map((a) => <li key={a.id} className="flex gap-2"><Icon name="hist" size={14} className="mt-0.5 text-ink-60" />{a.colaborador_nome} · {dataCurta(a.desde)} – {a.ate ? dataCurta(a.ate) : 'até ao fim'}</li>)}
          </ul>
        </div>
      )}
      {(m.error || remover.error) ? <div className="mt-3"><ErrorBox error={m.error ?? remover.error} /></div> : null}
    </Modal>
  )
}
