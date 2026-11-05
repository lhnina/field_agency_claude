import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AcaoIcone, Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { Credenciais, ModelosCredencial } from './Credenciais'
import { abrirFicheiro, api, apiForm, session } from '../lib/api'
import { dataCurta } from '../lib/format'
import type { DocumentoReg, EstadoDocumento, IdNome, Requisito, ResumoDoc, SituacaoDoc, TipoDocumento } from '../lib/types'

export const ESTADO_DOC: Record<EstadoDocumento, { label: string; tone: 'ok' | 'warn' | 'err' | 'neu' }> = {
  expirado: { label: 'Expirado', tone: 'err' },
  em_falta: { label: 'Em falta', tone: 'err' },
  a_expirar: { label: 'A expirar', tone: 'warn' },
  valido: { label: 'Válido', tone: 'ok' },
}

const pode = (perfis: string[]) => perfis.includes(session.user()?.perfil ?? '')
export const podeRegistarDocs = () => pode(['administrador', 'gestor', 'gestor_conta', 'rh', 'supervisor'])
const podeConfigurar = () => pode(['administrador', 'gestor', 'gestor_conta', 'rh'])

export default function Documentacao() {
  const [tab, setTab] = useState('documentos')
  return (
    <>
      <PageHeader crumb="Pessoas" title="Documentação" sub="Documentos dos colaboradores, validades e requisitos por função, cliente e cadeia.">
        <Seg label="Secção" value={tab} onChange={setTab} options={[
          { value: 'documentos', label: 'Documentos' }, { value: 'credenciais', label: 'Credenciais' }, { value: 'tipos', label: 'Tipos de documento' },
          { value: 'requisitos', label: 'Requisitos' }, { value: 'modelos', label: 'Modelos de credencial' }]} />
      </PageHeader>
      {tab === 'documentos' ? <Documentos /> : tab === 'credenciais' ? <Credenciais /> : tab === 'modelos' ? <ModelosCredencial />
        : tab === 'tipos' ? <Tipos /> : <Requisitos />}
    </>
  )
}

// ------------------------------------------------------------------ documentos
function Documentos() {
  const [sp, setSp] = useSearchParams()
  const colaborador = sp.get('colaborador')
  const q = useQuery({ queryKey: ['documentos'], queryFn: () => api<{ linhas: SituacaoDoc[]; resumo: ResumoDoc }>('/documentos') })
  const tipos = useQuery({ queryKey: ['tipos-documento'], queryFn: () => api<TipoDocumento[]>('/tipos-documento') })
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const [estado, setEstado] = useState<string>(sp.get('estado') ?? (sp.get('colaborador') ? 'todos' : 'problemas'))
  const [tipo, setTipo] = useState('')
  const [zona, setZona] = useState('')
  const [texto, setTexto] = useState('')
  const [dlg, setDlg] = useState<{ linha: SituacaoDoc; modo: 'novo' | 'corrigir' } | null>(null)

  const linhas = useMemo(() => (q.data?.linhas ?? []).filter((l) => {
    if (colaborador && String(l.colaborador_id) !== colaborador) return false
    if (estado === 'problemas' && !(l.obrigatorio && (l.estado === 'expirado' || l.estado === 'em_falta')) && l.estado !== 'a_expirar') return false
    if (estado !== 'problemas' && estado !== 'todos' && l.estado !== estado) return false
    if (tipo && String(l.tipo_documento_id) !== tipo) return false
    if (zona && l.zona !== zona) return false
    const t = texto.trim().toLowerCase()
    return !t || l.colaborador.toLowerCase().includes(t) || l.numero_colaborador.includes(t) || (l.documento?.numero ?? '').toLowerCase().includes(t)
  }), [q.data, estado, tipo, zona, texto, colaborador])
  const nomeColab = colaborador ? q.data?.linhas.find((l) => String(l.colaborador_id) === colaborador)?.colaborador : null

  if (q.isLoading) return <Card><Loading /></Card>
  if (q.error || !q.data) return <ErrorBox error={q.error} />
  const r = q.data.resumo
  const kpis: { k: string; label: string; v: number; sub: string; cls: string }[] = [
    { k: 'expirado', label: 'Expirados', v: r.expirados, sub: 'documentos obrigatórios', cls: r.expirados ? 'text-err-fg' : '' },
    { k: 'em_falta', label: 'Em falta', v: r.em_falta, sub: 'documentos obrigatórios', cls: r.em_falta ? 'text-err-fg' : '' },
    { k: 'a_expirar', label: 'A expirar', v: r.a_expirar, sub: 'dentro do prazo de aviso', cls: r.a_expirar ? 'text-warn-fg' : '' },
    { k: 'valido', label: 'Válidos', v: r.validos, sub: `${r.colaboradores_com_problemas} colaboradores com pendências`, cls: '' },
  ]
  return (
    <>
      <Card className="overflow-hidden">
        <div className="grid grid-cols-2 md:grid-cols-4 border-b border-line-soft">
          {kpis.map((x, i) => (
            <button key={x.k} type="button" onClick={() => setEstado(estado === x.k ? 'problemas' : x.k)}
              className={`text-left px-[18px] py-3.5 hover:bg-[#F6F8F7] ${i < 3 ? 'md:border-r border-line-soft' : ''} ${estado === x.k ? 'bg-petrol-50' : ''}`}>
              <div className="text-xs text-ink-60">{x.label}</div>
              <div className={`text-xl font-semibold tracking-[-0.02em] mt-0.5 num ${x.cls}`}>{x.v}</div>
              <div className="text-xs text-ink-60">{x.sub}</div>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
          {colaborador && (
            <span className="inline-flex items-center gap-1.5 h-9 pl-3 pr-1.5 rounded-lg border border-petrol-600 bg-petrol-50 text-[13px] text-petrol-700">
              Colaborador: <b className="font-semibold">{nomeColab ?? '…'}</b>
              <button type="button" aria-label="Mostrar todos os colaboradores" title="Mostrar todos os colaboradores" className="p-1 rounded hover:bg-petrol-100"
                onClick={() => { const n = new URLSearchParams(sp); n.delete('colaborador'); setSp(n) }}><Icon name="x" size={14} /></button>
            </span>
          )}
          <div className="relative">
            <Icon name="search" size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-60" />
            <input aria-label="Pesquisar" className="inp !pl-8 w-[220px]" placeholder="Colaborador, n.º ou documento" value={texto} onChange={(e) => setTexto(e.target.value)} />
          </div>
          <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">Mostrar
            <select aria-label="Estado" className="outline-none font-medium text-ink bg-transparent" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="problemas">Pendências</option><option value="todos">Todos</option>
              <option value="expirado">Expirados</option><option value="em_falta">Em falta</option><option value="a_expirar">A expirar</option><option value="valido">Válidos</option>
            </select></label>
          <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">Documento
            <select aria-label="Tipo de documento" className="outline-none font-medium text-ink bg-transparent" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todos</option>{tipos.data?.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select></label>
          <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">Zona
            <select aria-label="Zona" className="outline-none font-medium text-ink bg-transparent" value={zona} onChange={(e) => setZona(e.target.value)}>
              <option value="">Todas</option>{zonas.data?.map((z) => <option key={z.id} value={z.nome}>{z.nome}</option>)}
            </select></label>
          <span className="flex-1" />
          <span className="text-[12.5px] text-ink-60">{linhas.length} linha{linhas.length === 1 ? '' : 's'}</span>
        </div>
        {!linhas.length ? <Empty title={estado === 'problemas' ? 'Sem pendências documentais' : 'Sem documentos com estes filtros'} /> : (
          <div className="overflow-x-auto">
            <TabelaDocs linhas={linhas} mostrarColaborador onAcao={(linha, modo) => setDlg({ linha, modo })} />
          </div>
        )}
      </Card>
      <p className="text-[12.5px] text-ink-60 flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />
        Documentos obrigatórios em falta ou expirados geram avisos no planeamento, mas não impedem a afetação. As consultas aos anexos ficam registadas.</p>
      {dlg && <DocumentoDialog linha={dlg.linha} modo={dlg.modo} onClose={() => setDlg(null)} />}
    </>
  )
}

export function TabelaDocs({ linhas, mostrarColaborador, onAcao }: { linhas: SituacaoDoc[]; mostrarColaborador?: boolean; onAcao: (l: SituacaoDoc, modo: 'novo' | 'corrigir') => void }) {
  const toast = useToast()
  const regista = podeRegistarDocs()
  return (
    <table className="tbl">
      <thead><tr>
        {mostrarColaborador && <th>Colaborador</th>}<th>Documento</th><th>N.º</th><th>Validade</th><th>Estado</th><th>Anexo</th><th />
      </tr></thead>
      <tbody>{linhas.map((l) => {
        const d = l.documento
        const e = ESTADO_DOC[l.estado]
        return (
          <tr key={`${l.colaborador_id}-${l.tipo_documento_id}`}>
            {mostrarColaborador && (
              <td><div className="flex items-center gap-2.5"><Avatar nome={l.colaborador} />
                <div><Link to={`/colaboradores?id=${l.colaborador_id}`} className="font-medium hover:underline">{l.colaborador}</Link>
                  <div className="text-xs text-ink-60">{[`N.º ${l.numero_colaborador}`, l.funcao, l.zona].filter(Boolean).join(' · ')}</div></div></div></td>
            )}
            <td><div className="font-medium">{l.tipo}</div>
              <div className="text-xs text-ink-60">{l.obrigatorio ? `Obrigatório: ${l.motivo}` : 'Não obrigatório'}</div></td>
            <td className="num text-[12.5px]">{d?.numero ?? '—'}</td>
            <td className="num text-[12.5px] whitespace-nowrap">{d ? (l.tem_validade ? dataCurta(d.validade) : 'Sem validade') : '—'}</td>
            <td><Badge tone={l.estado === 'em_falta' && !l.obrigatorio ? 'neu' : e.tone} dot>{e.label}</Badge></td>
            <td>{d?.ficheiro_nome ? (
              <button type="button" className="flex items-center gap-1 text-[12.5px] text-petrol-600 hover:underline max-w-[180px]" title={d.ficheiro_nome}
                onClick={() => abrirFicheiro(`/documentos/${d.id}/ficheiro`).catch((x) => toast(x instanceof Error ? x.message : 'Erro', 'err'))}>
                <Icon name="file" size={14} className="flex-none" /><span className="truncate">{d.ficheiro_nome}</span></button>
            ) : <span className="text-ink-60">—</span>}</td>
            <td className="text-right whitespace-nowrap">{regista && (d ? <>
              <AcaoIcone icon="edit" label={`Corrigir ${l.tipo}`} onClick={() => onAcao(l, 'corrigir')} />
              <AcaoIcone icon="sync" label={`Renovar ${l.tipo}`} onClick={() => onAcao(l, 'novo')}
                className={l.estado === 'valido' ? '' : '!text-petrol-600 bg-petrol-50 hover:!bg-petrol-100'} />
            </> : <AcaoIcone icon="plus" label={`Registar ${l.tipo}`} onClick={() => onAcao(l, 'novo')} className="!text-petrol-600 bg-petrol-50 hover:!bg-petrol-100" />)}</td>
          </tr>
        )
      })}</tbody>
    </table>
  )
}

/** Registar, renovar ou corrigir um documento de um colaborador. Sem linha → escolher o tipo. */
export function DocumentoDialog({ linha, modo, colaborador, onClose }: {
  linha?: SituacaoDoc; modo: 'novo' | 'corrigir'; colaborador?: { id: number; nome: string }; onClose: () => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const tipos = useQuery({ queryKey: ['tipos-documento'], queryFn: () => api<TipoDocumento[]>('/tipos-documento') })
  const d = modo === 'corrigir' ? linha?.documento : null
  const colab = colaborador ?? { id: linha!.colaborador_id, nome: linha!.colaborador }
  const [f, setF] = useState({ tipo: linha ? String(linha.tipo_documento_id) : '', numero: d?.numero ?? '', emissao: d?.emissao ?? '', validade: d?.validade ?? '', observacoes: d?.observacoes ?? '' })
  const [ficheiro, setFicheiro] = useState<File | null>(null)
  const tipo = tipos.data?.find((t) => String(t.id) === f.tipo)
  const temValidade = linha ? linha.tem_validade : tipo?.tem_validade ?? true
  const erroVal = temValidade && !f.validade ? 'Indique a validade' : f.emissao && f.validade && f.validade < f.emissao ? 'Anterior à emissão' : null
  const erroFich = ficheiro && ficheiro.size > 10 * 1024 * 1024 ? 'O anexo não pode ter mais de 10 MB' : null
  const m = useMutation({
    mutationFn: () => {
      const dados = { numero: f.numero, emissao: f.emissao, validade: temValidade ? f.validade : '', observacoes: f.observacoes, ficheiro }
      return d ? apiForm<DocumentoReg>(`/documentos/${d.id}`, 'PUT', dados)
        : apiForm<DocumentoReg>(`/colaboradores/${colab.id}/documentos`, 'POST', { ...dados, tipo_documento_id: f.tipo })
    },
    onSuccess: () => {
      ['documentos', 'documentos-colaborador', 'planeamento', 'dashboard', 'tipos-documento'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
      toast(d ? 'Documento corrigido' : linha?.documento ? 'Documento renovado; o anterior ficou no histórico' : 'Documento registado'); onClose()
    },
  })
  const titulo = d ? `Corrigir ${linha!.tipo}` : linha?.documento ? `Renovar ${linha.tipo}` : linha ? `Registar ${linha.tipo}` : 'Registar documento'
  return (
    <Modal title={`${titulo} · ${colab.nome}`} onClose={onClose} width={600}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="primary" loading={m.isPending} disabled={!f.tipo || !!erroVal || !!erroFich} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        {!linha && <Field label="Tipo de documento" className="col-span-2">{(id) => (
          <select id={id} className="inp" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>
            <option value="">Escolher…</option>{tipos.data?.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
          </select>)}</Field>}
        <Field label="Número / referência">{(id) => <input id={id} className="inp" value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} />}</Field>
        <Field label="Data de emissão">{(id) => <DataInput id={id} limpar value={f.emissao} onChange={(v) => setF({ ...f, emissao: v })} />}</Field>
        {temValidade
          ? <Field label="Válido até" error={f.validade || f.emissao ? erroVal : null}>{(id) => <DataInput id={id} invalid={!!(f.validade && erroVal)} value={f.validade} min={f.emissao || undefined} onChange={(v) => setF({ ...f, validade: v })} />}</Field>
          : <div className="text-[12.5px] text-ink-60 self-end pb-2.5">Este tipo de documento não tem validade.</div>}
        <Field label="Anexo (PDF ou imagem, até 10 MB)" error={erroFich} hint={d?.ficheiro_nome && !ficheiro ? `Atual: ${d.ficheiro_nome}` : undefined}>{(id) => (
          <input id={id} type="file" accept="application/pdf,image/*" className="block w-full text-[13px] file:mr-3 file:h-9 file:px-3 file:rounded-lg file:border file:border-line-strong file:bg-white file:text-[13px] file:font-medium hover:file:bg-bg"
            onChange={(e) => setFicheiro(e.target.files?.[0] ?? null)} />)}</Field>
        <Field label="Observações" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      {linha?.documento && modo === 'novo' && <p className="text-xs text-ink-60 mt-3">O documento atual passa para o histórico do colaborador.</p>}
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

// ------------------------------------------------------------------ tipos
function Tipos() {
  const [inativos, setInativos] = useState(false)
  const q = useQuery({ queryKey: ['tipos-documento', inativos], queryFn: () => api<TipoDocumento[]>('/tipos-documento', { params: { inativos } }) })
  const [edit, setEdit] = useState<TipoDocumento | 'novo' | null>(null)
  const qc = useQueryClient()
  const toast = useToast()
  const estado = useMutation({
    mutationFn: (t: TipoDocumento) => api(`/tipos-documento/${t.id}/estado`, { method: 'POST', body: { ativo: !t.ativo } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tipos-documento'] }); qc.invalidateQueries({ queryKey: ['documentos'] }); toast('Tipo de documento atualizado') },
  })
  const cfg = podeConfigurar()
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-3 px-[18px] py-3 border-b border-line-soft">
        <h3 className="text-[14.5px] font-semibold">Tipos de documento</h3>
        <span className="flex-1" />
        <label className="flex items-center gap-2 text-[13px] text-ink-80"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={inativos} onChange={(e) => setInativos(e.target.checked)} />Mostrar inativos</label>
        {cfg && <Button size="sm" variant="primary" icon="plus" onClick={() => setEdit('novo')}>Novo tipo</Button>}
      </div>
      {q.isLoading ? <Loading /> : !q.data?.length ? <Empty title="Sem tipos de documento" /> : (
        <table className="tbl">
          <thead><tr><th>Documento</th><th>Validade</th><th className="text-right">Aviso</th><th className="text-right">Requisitos</th><th className="text-right">Entregues</th><th>Estado</th><th /></tr></thead>
          <tbody>{q.data.map((t) => (
            <tr key={t.id} className={t.ativo ? '' : '[&>td]:!bg-[#EEF0EC] text-ink-60'}>
              <td className="font-medium">{cfg ? <button type="button" className="hover:underline text-left" onClick={() => setEdit(t)}>{t.nome}</button> : t.nome}</td>
              <td>{t.tem_validade ? 'Com validade' : 'Sem validade'}</td>
              <td className="text-right num">{t.tem_validade ? `${t.dias_aviso} dias antes` : '—'}</td>
              <td className="text-right num">{t.requisitos}</td>
              <td className="text-right num">{t.documentos}</td>
              <td>{t.ativo ? <Badge tone="ok" dot>Ativo</Badge> : <Badge dot>Inativo</Badge>}</td>
              <td className="text-right whitespace-nowrap">{cfg && <>
                <AcaoIcone icon="edit" label={`Editar ${t.nome}`} onClick={() => setEdit(t)} />
                <AcaoIcone icon={t.ativo ? 'trash' : 'hist'} tom={t.ativo ? 'perigo' : 'neutro'} label={`${t.ativo ? 'Desativar' : 'Reativar'} ${t.nome}`}
                  loading={estado.isPending && estado.variables?.id === t.id} onClick={() => estado.mutate(t)} />
              </>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {edit && <TipoDialog t={edit === 'novo' ? null : edit} onClose={() => setEdit(null)} />}
    </Card>
  )
}

function TipoDialog({ t, onClose }: { t: TipoDocumento | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [f, setF] = useState({ nome: t?.nome ?? '', tem_validade: t?.tem_validade ?? true, dias_aviso: String(t?.dias_aviso ?? 30) })
  const m = useMutation({
    mutationFn: () => api(t ? `/tipos-documento/${t.id}` : '/tipos-documento', { method: t ? 'PUT' : 'POST', body: { ...f, dias_aviso: Number(f.dias_aviso) || 0 } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tipos-documento'] }); qc.invalidateQueries({ queryKey: ['documentos'] }); toast(t ? 'Tipo atualizado' : 'Tipo criado'); onClose() },
  })
  return (
    <Modal title={t ? `Editar ${t.nome}` : 'Novo tipo de documento'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome.trim()} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Nome" className="col-span-2">{(id) => <input id={id} className="inp" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} placeholder="Ex.: Formação HACCP" />}</Field>
        <label className="col-span-2 flex items-center gap-2 text-[13.5px]"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={f.tem_validade} onChange={(e) => setF({ ...f, tem_validade: e.target.checked })} />Tem data de validade</label>
        {f.tem_validade && <Field label="Avisar com antecedência (dias)" hint="Passa a «A expirar» este número de dias antes da validade">{(id) => <input id={id} inputMode="numeric" className="inp num" value={f.dias_aviso} onChange={(e) => setF({ ...f, dias_aviso: e.target.value.replace(/\D/g, '') })} />}</Field>}
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

// ------------------------------------------------------------------ requisitos
function Requisitos() {
  const q = useQuery({ queryKey: ['requisitos'], queryFn: () => api<Requisito[]>('/requisitos-documentais') })
  const [novo, setNovo] = useState<Requisito | 'novo' | null>(null)
  const qc = useQueryClient()
  const toast = useToast()
  const remover = useMutation({
    mutationFn: (r: Requisito) => api(`/requisitos-documentais/${r.id}`, { method: 'DELETE' }),
    onSuccess: () => { ['requisitos', 'documentos', 'tipos-documento', 'planeamento'].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast('Requisito removido') },
  })
  const cfg = podeConfigurar()
  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex items-center gap-3 px-[18px] py-3 border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Documentos obrigatórios</h3>
          <span className="text-[12.5px] text-ink-60">a quem se aplica cada documento</span>
          <span className="flex-1" />
          {cfg && <Button size="sm" variant="primary" icon="plus" onClick={() => setNovo('novo')}>Novo requisito</Button>}
        </div>
        {q.isLoading ? <Loading /> : !q.data?.length ? <Empty title="Sem requisitos">Sem requisitos, nenhum documento é obrigatório.</Empty> : (
          <table className="tbl">
            <thead><tr><th>Documento</th><th>Função</th><th>Cliente</th><th>Cadeia (insígnia)</th><th /></tr></thead>
            <tbody>{q.data.map((r) => (
              <tr key={r.id}>
                <td className="font-medium">{r.tipo}</td>
                <td>{r.funcao ?? <span className="text-ink-60">Qualquer</span>}</td>
                <td>{r.cliente ?? <span className="text-ink-60">Qualquer</span>}</td>
                <td>{r.insignia ?? <span className="text-ink-60">Qualquer</span>}</td>
                <td className="text-right whitespace-nowrap">{cfg && <AcaoIcone icon="edit" label={`Editar requisito ${r.tipo}`} onClick={() => setNovo(r)} />}{cfg && <AcaoIcone icon="trash" tom="perigo" label={`Remover requisito ${r.tipo}`} loading={remover.isPending && remover.variables?.id === r.id} onClick={() => remover.mutate(r)} />}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Card>
      <p className="text-[12.5px] text-ink-60 flex gap-1.5"><Icon name="alert" size={14} className="mt-0.5" />
        «Qualquer» quer dizer que esse critério não restringe. Um requisito só com o documento aplica-se a todos os colaboradores; com cliente ou cadeia, aplica-se a quem presta serviço nesse cliente ou nessa cadeia.</p>
      {novo && <RequisitoDialog r={novo === 'novo' ? null : novo} onClose={() => setNovo(null)} />}
    </>
  )
}

function RequisitoDialog({ r, onClose }: { r: Requisito | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const tipos = useQuery({ queryKey: ['tipos-documento'], queryFn: () => api<TipoDocumento[]>('/tipos-documento') })
  const funcoes = useQuery({ queryKey: ['funcoes'], queryFn: () => api<IdNome[]>('/funcoes') })
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<IdNome[]>('/clientes') })
  const insignias = useQuery({ queryKey: ['insignias'], queryFn: () => api<IdNome[]>('/insignias') })
  const [f, setF] = useState({ tipo_documento_id: r ? String(r.tipo_documento_id) : '', funcao: r?.funcao ?? '',
    cliente_id: r?.cliente_id ? String(r.cliente_id) : '', insignia_id: r?.insignia_id ? String(r.insignia_id) : '' })
  const m = useMutation({
    mutationFn: () => api(r ? `/requisitos-documentais/${r.id}` : '/requisitos-documentais', { method: r ? 'PUT' : 'POST', body: {
      tipo_documento_id: Number(f.tipo_documento_id), funcao: f.funcao || null,
      cliente_id: f.cliente_id ? Number(f.cliente_id) : null, insignia_id: f.insignia_id ? Number(f.insignia_id) : null } }),
    onSuccess: () => { ['requisitos', 'documentos', 'tipos-documento', 'planeamento'].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast(r ? 'Requisito atualizado' : 'Requisito criado'); onClose() },
  })
  const sel = (k: keyof typeof f, label: string, ops: { v: string; l: string }[], vazio = 'Qualquer') => (
    <Field label={label}>{(id) => (
      <select id={id} className="inp" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}>
        <option value="">{vazio}</option>{ops.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>)}</Field>
  )
  return (
    <Modal title={r ? 'Editar requisito documental' : 'Novo requisito documental'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.tipo_documento_id} onClick={() => m.mutate()}>{r ? 'Guardar' : 'Criar'}</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <div className="col-span-2">{sel('tipo_documento_id', 'Documento obrigatório', (tipos.data ?? []).map((t) => ({ v: String(t.id), l: t.nome })), 'Escolher…')}</div>
        {sel('funcao', 'Para a função', (funcoes.data ?? []).map((x) => ({ v: x.nome, l: x.nome })))}
        {sel('cliente_id', 'Nos serviços do cliente', (clientes.data ?? []).map((c) => ({ v: String(c.id), l: c.nome })))}
        {sel('insignia_id', 'Nas lojas da cadeia', (insignias.data ?? []).map((c) => ({ v: String(c.id), l: c.nome })))}
      </div>
      <p className="text-xs text-ink-60 mt-3">Os critérios combinam-se: por exemplo, função Promotora + cliente Nata Doce aplica-se só às promotoras que trabalham para esse cliente.</p>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
