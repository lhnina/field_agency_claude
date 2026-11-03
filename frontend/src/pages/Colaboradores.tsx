import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Bar, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { CredenciaisColaborador } from './Credenciais'
import { abrirFicheiro, api } from '../lib/api'
import { DocumentoDialog, ESTADO_DOC, podeRegistarDocs } from './Documentacao'
import { BotaoEstado, MostrarInativos } from '../components/Estado'
import { AREA, VINCULO, dataCurta, eur, horas } from '../lib/format'
import type { Colaborador, DocumentoReg, IdNome, ResumoDoc, SituacaoDoc, Vinculo } from '../lib/types'

const DL = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D']
const SEGMENTOS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' }, { value: 'muito_curta_duracao', label: 'Muito curta duração' }, { value: 'recibos_verdes', label: 'Recibos verdes' },
  { value: 'a_termo', label: 'A termo' }, { value: 'sem_termo', label: 'Sem termo' },
]

export default function Colaboradores() {
  const [vinculo, setVinculo] = useState('')
  const [q, setQ] = useState('')
  const [inativos, setInativos] = useState(false)
  const [zona, setZona] = useState('')
  const nav = useNavigate()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const [sp] = useSearchParams()
  const [sel, setSel] = useState<number | null>(sp.get('id') ? Number(sp.get('id')) : null)
  const [edit, setEdit] = useState<Colaborador | 'novo' | null>(null)
  const lista = useQuery({ queryKey: ['colaboradores', vinculo, q, inativos, zona], queryFn: () => api<Colaborador[]>('/colaboradores', { params: { vinculo, q, inativos, zona_id: zona } }) })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const itens = lista.data ?? []
  const atual = itens.find((c) => c.id === sel) ?? itens[0]
  const nomeSup = (id: number | null) => sups.data?.find((s) => s.id === id)?.nome ?? '—'

  return (
    <>
      <PageHeader crumb="Pessoas" title="Colaboradores" sub={`${itens.filter((c) => c.ativo).length} colaboradores ativos${vinculo ? ' neste segmento' : ''}`}>
        <Button variant="primary" icon="plus" onClick={() => setEdit('novo')}>Novo colaborador</Button>
      </PageHeader>
      <div className="flex flex-wrap items-start gap-4">
        <Card className="flex-[999_1_560px] overflow-hidden">
          <div role="tablist" aria-label="Segmentos" className="flex gap-0.5 border-b border-line px-[18px]">
            {SEGMENTOS.map((s) => (
              <button key={s.value} type="button" role="tab" aria-selected={vinculo === s.value} onClick={() => setVinculo(s.value)}
                className={`h-10 px-3 text-[13.5px] -mb-px border-b-2 ${vinculo === s.value ? 'border-petrol-600 text-ink font-medium' : 'border-transparent text-ink-60 hover:text-ink'}`}>{s.label}</button>
            ))}
          </div>
          <div className="px-3.5 py-3 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 h-[34px] w-[280px] px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
              <Icon name="search" size={16} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou n.º" aria-label="Pesquisar colaboradores" className="flex-1 min-w-0 bg-transparent outline-none text-[13.5px] text-ink" />
            </label>
            <label className={`inline-flex items-center gap-1.5 h-8 pl-2.5 pr-1 rounded-md border text-[13px] ${zona ? 'border-petrol-600 bg-[#E9F4F2] text-petrol-700' : 'border-line-strong bg-white text-ink-80'}`}>Zona:
              <select value={zona} onChange={(e) => setZona(e.target.value)} className="bg-transparent font-medium text-ink outline-none">
                <option value="">Todas</option>{zonas.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}
              </select>
            </label>
            <MostrarInativos value={inativos} onChange={setInativos} />
          </div>
          {lista.isLoading ? <Loading /> : lista.error ? <div className="p-4"><ErrorBox error={lista.error} /></div> : itens.length === 0 ? <Empty title="Sem colaboradores" /> : (
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>Colaborador</th><th>Vínculo</th><th>Zona</th><th>Disponibilidade</th><th>Carga afetada/semana</th><th>Supervisor</th><th className="text-right">Custo/hora</th></tr></thead>
                <tbody>
                  {itens.map((c, i) => (
                    <tr key={c.id} className={`${atual?.id === c.id ? '[&>td]:!bg-[#EAF4F2]' : ''} ${c.ativo ? '' : 'opacity-60'}`}>
                      <td>
                        <div className="flex items-center gap-2.5">
                          <Avatar nome={c.nome} tone={i} />
                          <div><button type="button" onClick={() => setSel(c.id)} className="font-medium text-[13.5px] hover:text-petrol-600 hover:underline text-left">{c.nome}{!c.ativo && <span className="ml-2 align-middle"><Badge>Inativo</Badge></span>}</button>
                            <div className="text-xs text-ink-60">N.º {c.numero}{c.funcao ? ` · ${c.funcao}` : ''}</div></div>
                        </div>
                      </td>
                      <td><Badge tone={VINCULO[c.vinculo].tone}>{VINCULO[c.vinculo].label}</Badge></td>
                      <td className="text-[12.5px]">{c.zona?.nome ?? <span className="text-ink-60">—</span>}</td>
                      <td><Disp d={c.disponibilidade} /></td>
                      <td><Carga h={Number(c.horas_afetadas)} prestador={c.vinculo === 'recibos_verdes'} /></td>
                      <td className="text-[12.5px] text-ink-60">{nomeSup(c.supervisor_id)}</td>
                      <td className="text-right num">{eur(c.custo_hora)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {atual && (
          <Card className="flex-[0_1_400px] min-w-[320px]">
            <div className="flex gap-3.5 items-start p-[18px]">
              <Avatar nome={atual.nome} size={52} />
              <div className="flex-1 min-w-0">
                <div className="text-[17px] font-semibold tracking-[-0.01em]">{atual.nome}</div>
                <div className="text-[12.5px] text-ink-60">N.º {atual.numero}{atual.funcao ? ` · ${atual.funcao}` : ''}</div>
                <div className="flex gap-1.5 mt-2">{atual.ativo ? <Badge tone="ok" dot>Ativo</Badge> : <Badge dot>Inativo</Badge>}<Badge tone={VINCULO[atual.vinculo].tone}>{VINCULO[atual.vinculo].label}</Badge></div>
              </div>
              <Button size="sm" variant="primary" icon="edit" onClick={() => setEdit(atual)}>Editar</Button>
            </div>
            {atual.vinculo === 'recibos_verdes' && <div className="px-[18px] pb-3"><Aviso>Prestador independente: os serviços são propostos e aceites por ele, sem escala imposta.</Aviso></div>}
            <Indicadores id={atual.id} vinculo={atual.vinculo} />
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-[18px] py-3.5 border-t border-line-soft">
              {[['Supervisor', nomeSup(atual.supervisor_id)], ['Zona', atual.zona?.nome ?? '—'], ['Início', dataCurta(atual.data_inicio)], ['Custo/hora', eur(atual.custo_hora)],
                ['Telemóvel', atual.telefone ?? '—'], ['Email', atual.email ?? '—']].map(([k, v]) => (
                <div key={k} className="min-w-0"><dt className="text-xs text-ink-60">{k}</dt><dd className="text-[13.5px] font-medium truncate">{v}</dd></div>
              ))}
            </dl>
            <Afetacoes id={atual.id} total={Number(atual.horas_afetadas)} prestador={atual.vinculo === 'recibos_verdes'}
              onPlaneamento={() => nav(`/planeamento?colaborador=${atual.id}${atual.zona_id ? `&zona=${atual.zona_id}` : ''}`)} />
            <DocumentosColab id={atual.id} nome={atual.nome} />
            <CredenciaisColaborador id={atual.id} nome={atual.nome} />
            <div className="px-[18px] py-3.5 border-t border-line-soft">
              <div className="text-[13px] font-semibold mb-2">Disponibilidade semanal</div>
              <Disp d={atual.disponibilidade} big />
            </div>
            <div className="flex justify-end px-[18px] py-3 border-t border-line-soft">
              <BotaoEstado url={`/colaboradores/${atual.id}/estado`} ativo={atual.ativo} nome={atual.nome} invalidar={['colaboradores']} />
            </div>
          </Card>
        )}
      </div>
      {edit && <ColabDialog c={edit === 'novo' ? null : edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function Carga({ h, prestador }: { h: number; prestador: boolean }) {
  const pct = (h / 40) * 100
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <span className="num text-[13px] font-medium w-11">{horas(h)}</span>
      {!prestador && <div className="flex-1"><Bar pct={pct} tone={pct > 100 ? 'err' : pct >= 95 ? 'warn' : 'ok'} /></div>}
      {prestador && <span className="text-xs text-ink-60">prestador</span>}
    </div>
  )
}

type Af = { linha_id: number; loja: string; cliente: string; contrato_id: number; contrato_numero: string; tipo: 'REP' | 'PRO' | 'LOG' | 'EQF'; horas_semana: number; dias: string[]; desde: string; ate: string | null }
function Afetacoes({ id, total, prestador, onPlaneamento }: { id: number; total: number; prestador: boolean; onPlaneamento: () => void }) {
  const q = useQuery({ queryKey: ['colaborador-afetacoes', id], queryFn: () => api<Af[]>(`/colaboradores/${id}/afetacoes`) })
  return (
    <div className="px-[18px] py-3.5 border-t border-line-soft">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-[13px] font-semibold">Lojas afetas</div>
        <span className="text-[12.5px] text-ink-60 num">{horas(total)} por semana{prestador ? '' : ' de 40 h'}</span>
        <span className="flex-1" />
        <Button size="sm" icon="cal" onClick={onPlaneamento}>Ver no planeamento</Button>
      </div>
      <ul className="flex flex-col gap-2">
        {q.data?.map((a) => (
          <li key={a.linha_id} className="text-[13px]">
            <div className="flex items-center gap-2"><span className={`w-2 h-2 rounded-sm ${AREA[a.tipo].sq}`} /><span className="font-medium">{a.loja}</span><span className="flex-1" /><span className="num">{horas(a.horas_semana)}</span></div>
            <div className="text-xs text-ink-60 ml-4">{a.cliente} · <Link to={`/contratos/${a.contrato_id}`} className="font-mono text-petrol-600 hover:underline">{a.contrato_numero}</Link> · {a.dias.join(', ')}{a.ate ? ` · até ${dataCurta(a.ate)}` : ''}</div>
          </li>
        ))}
        {q.data?.length === 0 && <li className="text-[12.5px] text-ink-60">Sem lojas afetas. Use "Ver no planeamento" para lhe atribuir serviços por atribuir.</li>}
      </ul>
    </div>
  )
}

function DocumentosColab({ id, nome }: { id: number; nome: string }) {
  const q = useQuery({ queryKey: ['documentos-colaborador', id], queryFn: () => api<{ linhas: SituacaoDoc[]; resumo: ResumoDoc; historico: DocumentoReg[] }>(`/colaboradores/${id}/documentos`) })
  const [dlg, setDlg] = useState<{ linha?: SituacaoDoc; modo: 'novo' | 'corrigir' } | null>(null)
  const toast = useToast()
  const r = q.data?.resumo
  const pend = r ? r.expirados + r.em_falta : 0
  return (
    <div className="px-[18px] py-3.5 border-t border-line-soft">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-[13px] font-semibold">Documentação</div>
        {r && (pend ? <Badge tone="err" dot>{pend} pendente{pend > 1 ? 's' : ''}</Badge> : r.a_expirar ? <Badge tone="warn" dot>{r.a_expirar} a expirar</Badge> : <Badge tone="ok" dot>Em dia</Badge>)}
        <span className="flex-1" />
        {podeRegistarDocs() && <Button size="sm" icon="plus" onClick={() => setDlg({ modo: 'novo' })}>Documento</Button>}
      </div>
      <ul className="flex flex-col divide-y divide-line-soft">
        {q.data?.linhas.map((l) => {
          const d = l.documento
          return (
            <li key={l.tipo_documento_id} className="py-1.5 flex items-center gap-2 text-[13px]">
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{l.tipo}</div>
                <div className="text-xs text-ink-60 truncate">{d ? (l.tem_validade ? `Válido até ${dataCurta(d.validade)}` : 'Sem validade') : `Obrigatório: ${l.motivo}`}</div>
              </div>
              {d?.ficheiro_nome && <button type="button" aria-label={`Abrir anexo de ${l.tipo}`} title={d.ficheiro_nome} className="p-1 text-petrol-600 hover:bg-bg rounded"
                onClick={() => abrirFicheiro(`/documentos/${d.id}/ficheiro`).catch((x) => toast(x instanceof Error ? x.message : 'Erro', 'err'))}><Icon name="file" size={15} /></button>}
              <Badge tone={l.estado === 'em_falta' && !l.obrigatorio ? 'neu' : ESTADO_DOC[l.estado].tone} dot>{ESTADO_DOC[l.estado].label}</Badge>
              {podeRegistarDocs() && <Button size="sm" variant="ghost" onClick={() => setDlg({ linha: l, modo: 'novo' })}>{d ? 'Renovar' : 'Registar'}</Button>}
            </li>
          )
        })}
        {q.data?.linhas.length === 0 && <li className="text-[12.5px] text-ink-60 py-1">Sem documentos obrigatórios nem entregues.</li>}
      </ul>
      {!!q.data?.historico.length && <div className="text-xs text-ink-60 mt-1.5">{q.data.historico.length} documento{q.data.historico.length > 1 ? 's' : ''} anterior{q.data.historico.length > 1 ? 'es' : ''} no histórico · <Link to="/documentacao" className="text-petrol-600 hover:underline">Ver documentação</Link></div>}
      {dlg && <DocumentoDialog linha={dlg.linha} modo={dlg.modo} colaborador={{ id, nome }} onClose={() => setDlg(null)} />}
    </div>
  )
}

type Ind = { dias_trabalhados_ano: number; dias_planeados_ano: number; dias_contrato_atual?: number; alertas: { nivel: string; texto: string }[] }
function Indicadores({ id, vinculo }: { id: number; vinculo: Vinculo }) {
  const q = useQuery({ queryKey: ['indicadores', id], queryFn: () => api<Ind>(`/colaboradores/${id}/indicadores`) })
  if (!q.data) return null
  const d = q.data
  const total = d.dias_trabalhados_ano + d.dias_planeados_ano
  return (
    <div className="px-[18px] pb-3.5 flex flex-col gap-2.5">
      {d.alertas.map((a) => <Aviso key={a.texto} erro={a.nivel === 'erro'}>{a.texto}</Aviso>)}
      {vinculo === 'muito_curta_duracao' && (
        <div className="grid grid-cols-2 gap-3">
          <div><div className="text-xs text-ink-60">Dias no ano (máx. 70)</div><div className="text-[15px] font-semibold num">{d.dias_trabalhados_ano} trabalhados + {d.dias_planeados_ano} planeados</div>
            <div className="mt-1"><Bar pct={(total / 70) * 100} tone={total > 70 ? 'err' : total >= 56 ? 'warn' : 'ok'} /></div></div>
          <div><div className="text-xs text-ink-60">Contrato atual (máx. 35 dias)</div><div className="text-[15px] font-semibold num">{d.dias_contrato_atual ?? 0} dias</div>
            <div className="mt-1"><Bar pct={((d.dias_contrato_atual ?? 0) / 35) * 100} tone={(d.dias_contrato_atual ?? 0) > 35 ? 'err' : (d.dias_contrato_atual ?? 0) >= 28 ? 'warn' : 'ok'} /></div></div>
        </div>
      )}
      {vinculo !== 'muito_curta_duracao' && <div className="text-[12.5px] text-ink-60">{d.dias_trabalhados_ano} dias com serviço em {new Date().getFullYear()} · {d.dias_planeados_ano} planeados até ao fim do ano</div>}
    </div>
  )
}

function Aviso({ children, erro }: { children: React.ReactNode; erro?: boolean }) {
  return <div className={`rounded-[9px] px-3 py-2.5 text-[12.5px] flex gap-2 ${erro ? 'bg-err-bg text-err-fg' : 'bg-warn-bg text-[#6B4000]'}`}><Icon name="alert" size={16} />{children}</div>
}

function Disp({ d, big }: { d: string; big?: boolean }) {
  return (
    <div className="flex gap-[3px]" aria-label={`Disponível: ${DL.map((_x, i) => (d[i] === '1' ? ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'][i] : null)).filter(Boolean).join(', ')}`}>
      {DL.map((x, i) => (
        <span key={i} className={`grid place-items-center rounded font-medium ${big ? 'w-8 h-8 text-xs' : 'w-[17px] h-[17px] text-[10.5px]'} ${d[i] === '1' ? 'bg-petrol-100 text-[#0B4D47]' : 'bg-[#EDEFEC] text-ink-60'}`}>{x}</span>
      ))}
    </div>
  )
}

function ColabDialog({ c, onClose }: { c: Colaborador | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const funcoes = useQuery({ queryKey: ['funcoes'], queryFn: () => api<IdNome[]>('/funcoes') })
  const [f, setF] = useState({
    numero: c?.numero ?? '', nome: c?.nome ?? '', funcao: c?.funcao ?? '', email: c?.email ?? '', telefone: c?.telefone ?? '',
    vinculo: (c?.vinculo ?? 'a_termo') as Vinculo, data_inicio: c?.data_inicio ?? '', zona_id: c?.zona_id ? String(c.zona_id) : '',
    supervisor_id: c?.supervisor_id ? String(c.supervisor_id) : '', custo_hora: c?.custo_hora ?? '', disponibilidade: c?.disponibilidade ?? '1111100',
    data_nascimento: c?.data_nascimento ?? '', numero_identificacao: c?.numero_identificacao ?? '', niss: c?.niss ?? '',
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })
  const m = useMutation({
    mutationFn: () => api<Colaborador>(c ? `/colaboradores/${c.id}` : '/colaboradores', {
      method: c ? 'PUT' : 'POST',
      body: { ...f, funcao: f.funcao || null, email: f.email || null, telefone: f.telefone || null, data_inicio: f.data_inicio || null,
        zona_id: f.zona_id ? Number(f.zona_id) : null, supervisor_id: f.supervisor_id ? Number(f.supervisor_id) : null,
        custo_hora: Number(String(f.custo_hora).replace(',', '.')) || 0, ativo: c?.ativo ?? true,
        data_nascimento: f.data_nascimento || null, numero_identificacao: f.numero_identificacao.trim() || null, niss: f.niss.trim() || null },
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['colaboradores'] }); toast(c ? 'Ficha atualizada' : 'Colaborador criado'); onClose() },
  })
  return (
    <Modal title={c ? `Editar ${c.nome}` : 'Novo colaborador'} onClose={onClose} width={620}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome || !f.numero} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Nome">{(id) => <input id={id} className="inp" value={f.nome} onChange={set('nome')} />}</Field>
        <Field label="N.º">{(id) => <input id={id} className="inp" value={f.numero} onChange={set('numero')} />}</Field>
        <Field label="Função" hint="Lista em Configuração › Funções">{(id) => (
          <select id={id} className="inp" value={f.funcao} onChange={set('funcao')}>
            <option value="">—</option>
            {funcoes.data?.map((x) => <option key={x.id} value={x.nome}>{x.nome}</option>)}
            {f.funcao && !funcoes.data?.some((x) => x.nome === f.funcao) && <option value={f.funcao}>{f.funcao}</option>}
          </select>)}</Field>
        <Field label="Vínculo">{(id) => (
          <select id={id} className="inp" value={f.vinculo} onChange={set('vinculo')}>
            {Object.entries(VINCULO).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>)}</Field>
        <Field label="Zona">{(id) => <select id={id} className="inp" value={f.zona_id} onChange={set('zona_id')}><option value="">—</option>{zonas.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}</select>}</Field>
        <Field label="Supervisor">{(id) => <select id={id} className="inp" value={f.supervisor_id} onChange={set('supervisor_id')}><option value="">—</option>{sups.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}</select>}</Field>
        <Field label="Custo por hora (€)" hint="Pode ser definido um Custo Fixo por loja no contrato">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.custo_hora} onChange={set('custo_hora')} />}</Field>
        <Field label="Data de início">{(id) => <DataInput id={id} limpar value={f.data_inicio} onChange={(v) => setF({ ...f, data_inicio: v })} />}</Field>
        <Field label="Telemóvel">{(id) => <input id={id} className="inp" value={f.telefone} onChange={set('telefone')} />}</Field>
        <Field label="Email">{(id) => <input id={id} type="email" className="inp" value={f.email} onChange={set('email')} />}</Field>
        <div className="col-span-2 grid grid-cols-3 gap-3.5 pt-1 border-t border-line-soft">
          <div className="col-span-3 text-xs text-ink-60 pt-2">Identificação (usada nas credenciais)</div>
          <Field label="Data de nascimento">{(id) => <DataInput id={id} limpar value={f.data_nascimento} max={new Date().toISOString().slice(0, 10)} onChange={(v) => setF({ ...f, data_nascimento: v })} />}</Field>
          <Field label="Doc. de Identificação" hint="N.º do documento">{(id) => <input id={id} className="inp num" value={f.numero_identificacao} onChange={set('numero_identificacao')} />}</Field>
          <Field label="N.º Segurança Social">{(id) => <input id={id} inputMode="numeric" className="inp num" value={f.niss} onChange={set('niss')} />}</Field>
        </div>
        <div className="col-span-2">
          <div className="lbl mb-1.5">Disponibilidade semanal</div>
          <div className="flex gap-1.5">
            {['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((d, i) => {
              const on = f.disponibilidade[i] === '1'
              return <button key={d} type="button" aria-pressed={on} onClick={() => setF({ ...f, disponibilidade: f.disponibilidade.slice(0, i) + (on ? '0' : '1') + f.disponibilidade.slice(i + 1) })}
                className={`h-9 w-12 rounded-md text-[13px] font-medium border ${on ? 'bg-petrol-100 border-petrol-600 text-[#0B4D47]' : 'bg-white border-line-strong text-ink-60'}`}>{d}</button>
            })}
          </div>
        </div>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
