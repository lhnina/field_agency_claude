import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BotaoEstado, Facto, MostrarInativos } from '../components/Estado'
import { AreaBadge, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Seg, useToast } from '../components/ui'
import { api, session } from '../lib/api'
import { Tabela } from './Tabelas'
import { InsigniaLogo } from '../components/InsigniaLogo'
import { ESTADO_CONTRATO, eur, horas } from '../lib/format'
import type { Cliente, ContratoResumo, IdNome, Loja, TipoContrato } from '../lib/types'

type Tab = 'clientes' | 'lojas' | 'insignias' | 'zonas'

export default function ClientesLojas() {
  const [tab, setTab] = useState<Tab>('clientes')
  const [novo, setNovo] = useState(false)
  return (
    <>
      <PageHeader crumb="Comercial" title="Clientes e lojas">
        <Seg label="Secção" value={tab} onChange={(v) => setTab(v as Tab)}
          options={[{ value: 'clientes', label: 'Clientes' }, { value: 'lojas', label: 'Lojas' }, { value: 'insignias', label: 'Insígnias' }, { value: 'zonas', label: 'Zonas' }]} />
        {(tab === 'clientes' || tab === 'lojas') && <Button variant="primary" icon="plus" onClick={() => setNovo(true)}>{tab === 'lojas' ? 'Nova loja' : 'Novo cliente'}</Button>}
      </PageHeader>
      {tab === 'clientes' ? <Clientes /> : tab === 'lojas' ? <Lojas />
        : tab === 'insignias' ? <div className="max-w-[760px]"><Tabela key="insignias" path="insignias" logos titulo="Insígnias (cadeias de distribuição)" ajuda="Cadeias a que pertencem as lojas, por exemplo Continente, Pingo Doce ou Auchan." /></div>
        : <div className="max-w-[760px]"><Tabela key="zonas" path="zonas" titulo="Zonas" ajuda="Usadas nas lojas e nos colaboradores para o planeamento, as sugestões de substitutos e os feriados municipais." /></div>}
      {novo && (tab === 'lojas' ? <LojaDialog onClose={() => setNovo(false)} /> : <ClienteDialog onClose={() => setNovo(false)} />)}
    </>
  )
}

function Pesquisa({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="flex items-center gap-2 h-[34px] w-[280px] px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
      <Icon name="search" size={16} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} className="flex-1 min-w-0 bg-transparent outline-none text-[13.5px] text-ink" />
    </label>
  )
}

function NomeLink({ nome, ativo, onClick }: { nome: string; ativo: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="font-medium text-[13.5px] hover:text-petrol-600 hover:underline text-left">
      {nome}{!ativo && <span className="ml-2 align-middle"><Badge>Inativo</Badge></span>}
    </button>
  )
}

// ------------------------------------------------------------------ clientes
function Clientes() {
  const [q, setQ] = useState('')
  const [inativos, setInativos] = useState(false)
  const [sel, setSel] = useState<number | null>(null)
  const [edit, setEdit] = useState<Cliente | null>(null)
  const lista = useQuery({ queryKey: ['clientes', 'gestao', q, inativos], queryFn: () => api<Cliente[]>('/clientes', { params: { q, inativos } }) })
  const contratos = useQuery({ queryKey: ['contratos', ''], queryFn: () => api<ContratoResumo[]>('/contratos') })
  const itens = lista.data ?? []
  const atual = itens.find((c) => c.id === sel) ?? itens[0]
  const ativosPorCliente = (id: number) => (contratos.data ?? []).filter((c) => c.cliente_id === id && c.estado === 'ativo')
  return (
    <div className="flex flex-wrap items-start gap-4">
      <Card className="flex-[999_1_560px] overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-3.5 py-3 border-b border-line-soft">
          <Pesquisa value={q} onChange={setQ} placeholder="Nome ou NIF" />
          <MostrarInativos value={inativos} onChange={setInativos} />
          <span className="flex-1" /><span className="text-[12.5px] text-ink-60">{itens.length} clientes</span>
        </div>
        {lista.isLoading ? <Loading /> : lista.error ? <div className="p-4"><ErrorBox error={lista.error} /></div> : itens.length === 0 ? <Empty title="Sem clientes" /> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Cliente</th><th>Localidade</th><th>Gestor de conta</th><th className="text-right">Contratos ativos</th><th className="text-right">Valor mensal</th></tr></thead>
              <tbody>{itens.map((c) => {
                const ca = ativosPorCliente(c.id)
                return (
                  <tr key={c.id} className={`${atual?.id === c.id ? '[&>td]:!bg-[#EAF4F2]' : ''} ${c.ativo ? '' : 'opacity-60'}`}>
                    <td><NomeLink nome={c.nome} ativo={c.ativo} onClick={() => setSel(c.id)} />
                      <div className="text-xs text-ink-60">{[c.codigo_erp && `Código ERP ${c.codigo_erp}`, c.nif && `NIF ${c.nif}`].filter(Boolean).join(' · ') || '—'}</div></td>
                    <td className="text-[12.5px]">{c.localidade ?? '—'}</td>
                    <td className="text-[12.5px]">{c.gestor_conta?.nome ?? '—'}</td>
                    <td className="text-right num">{ca.length}</td>
                    <td className="text-right num">{ca.length ? eur(ca.reduce((s, x) => s + Number(x.valor_mensal), 0), 0) : '—'}</td>
                  </tr>
                )
              })}</tbody>
            </table>
          </div>
        )}
      </Card>
      {atual && (
        <Card className="flex-[0_1_400px] min-w-[320px]">
          <div className="flex gap-3.5 items-start p-[18px]">
            <span className="grid place-items-center w-[52px] h-[52px] rounded-xl bg-rep-bg text-rep-fg flex-none"><Icon name="store" size={24} /></span>
            <div className="flex-1 min-w-0">
              <div className="text-[17px] font-semibold tracking-[-0.01em]">{atual.nome}</div>
              <div className="text-[12.5px] text-ink-60">{[atual.nif && `NIF ${atual.nif}`, atual.codigo_erp && `Código ERP ${atual.codigo_erp}`].filter(Boolean).join(' · ') || 'Sem NIF'}</div>
              <div className="flex gap-1.5 mt-2">{atual.ativo ? <Badge tone="ok" dot>Ativo</Badge> : <Badge dot>Inativo</Badge>}</div>
            </div>
            <Button size="sm" variant="primary" icon="edit" onClick={() => setEdit(atual)}>Editar</Button>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-[18px] py-3.5 border-t border-line-soft">
            <Facto k="Gestor de conta" v={atual.gestor_conta?.nome} />
            <Facto k="Contacto" v={atual.contacto_nome} />
            <Facto k="Telefone" v={atual.telefone} href={atual.telefone ? `tel:${atual.telefone}` : undefined} />
            <Facto k="Email" v={atual.email} href={atual.email ? `mailto:${atual.email}` : undefined} />
            <div className="col-span-2"><Facto k="Morada" v={[atual.morada, [atual.codigo_postal, atual.localidade].filter(Boolean).join(' ')].filter(Boolean).join(', ')} /></div>
            <div className="col-span-2"><Facto k="Site" v={atual.url} href={atual.url ? (atual.url.startsWith('http') ? atual.url : `https://${atual.url}`) : undefined} /></div>
          </dl>
          {atual.observacoes && <div className="px-[18px] pb-3.5 text-[13px] text-ink-80 whitespace-pre-line">{atual.observacoes}</div>}
          <div className="px-[18px] py-3.5 border-t border-line-soft">
            <div className="text-[13px] font-semibold mb-2">Contratos</div>
            <ul className="flex flex-col gap-2">
              {(contratos.data ?? []).filter((c) => c.cliente_id === atual.id).map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-[13px]">
                  <Link to={`/contratos/${c.id}`} className="font-mono text-[12.5px] text-petrol-600 hover:underline whitespace-nowrap">{c.numero}</Link>
                  <AreaBadge tipo={c.tipo as TipoContrato} /><span className="flex-1" />
                  <Badge tone={ESTADO_CONTRATO[c.estado].tone}>{ESTADO_CONTRATO[c.estado].label}</Badge>
                  <span className="num w-[82px] text-right">{eur(c.valor_mensal, 0)}</span>
                </li>
              ))}
              {!(contratos.data ?? []).some((c) => c.cliente_id === atual.id) && <li className="text-[12.5px] text-ink-60">Sem contratos</li>}
            </ul>
          </div>
          <div className="flex justify-end px-[18px] py-3 border-t border-line-soft">
            <BotaoEstado url={`/clientes/${atual.id}/estado`} ativo={atual.ativo} nome={atual.nome} invalidar={['clientes']} />
          </div>
        </Card>
      )}
      {edit && <ClienteDialog cliente={edit} onClose={() => setEdit(null)} />}
    </div>
  )
}

function ClienteDialog({ cliente, onClose }: { cliente?: Cliente; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const campos = ['nome', 'nif', 'codigo_erp', 'morada', 'codigo_postal', 'localidade', 'telefone', 'email', 'url', 'contacto_nome', 'gestor_conta_id', 'observacoes'] as const
  const [f, setF] = useState<Record<string, string>>(() => {
    const o: Record<string, string> = {}
    campos.forEach((k) => { o[k] = cliente?.[k] != null ? String(cliente[k]) : '' })
    return o
  })
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value })
  const [marcas, setMarcas] = useState<string[]>(() => (cliente?.marcas ?? []).filter((x) => x.ativo !== false).map((x) => x.nome))
  const [novaMarca, setNovaMarca] = useState('')
  const juntarMarca = () => {
    const n = novaMarca.trim()
    if (n && !marcas.some((x) => x.toLowerCase() === n.toLowerCase())) setMarcas([...marcas, n])
    setNovaMarca('')
  }
  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {}
      campos.forEach((k) => { body[k] = f[k].trim() || null })
      body.nome = f.nome.trim()
      body.codigo_erp = f.codigo_erp ? Number(f.codigo_erp) : null
      body.gestor_conta_id = f.gestor_conta_id ? Number(f.gestor_conta_id) : null
      body.marcas = novaMarca.trim() && !marcas.some((x) => x.toLowerCase() === novaMarca.trim().toLowerCase()) ? [...marcas, novaMarca.trim()] : marcas
      return api(cliente ? `/clientes/${cliente.id}` : '/clientes', { method: cliente ? 'PUT' : 'POST', body })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['clientes'] }); toast(cliente ? 'Cliente atualizado' : 'Cliente criado'); onClose() },
  })
  const gestores = useQuery({ queryKey: ['gestores-conta'], queryFn: () => api<IdNome[]>('/utilizadores/gestores-conta') })
  const souGestorConta = session.user()?.perfil === 'gestor_conta'
  const erpErr = f.codigo_erp && !/^\d+$/.test(f.codigo_erp) ? 'Só números' : null
  const txt = (k: string, label: string, cls = '', type = 'text') => (
    <Field label={label} className={cls}>{(id) => <input id={id} type={type} className="inp" value={f[k]} onChange={set(k)} />}</Field>
  )
  return (
    <Modal title={cliente ? `Editar ${cliente.nome}` : 'Novo cliente'} onClose={onClose} width={680}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome.trim() || !!erpErr} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-3 gap-3.5">
        {txt('nome', 'Nome', 'col-span-2')}
        {txt('nif', 'NIF')}
        {txt('morada', 'Morada', 'col-span-3')}
        {txt('codigo_postal', 'Código postal')}{txt('localidade', 'Localidade')}
        <Field label="Código de cliente no ERP" error={erpErr}>{(id) => <input id={id} inputMode="numeric" className={`inp ${erpErr ? 'inp-err' : ''}`} value={f.codigo_erp} onChange={set('codigo_erp')} />}</Field>
        {txt('telefone', 'Telefone', '', 'tel')}{txt('email', 'Email', '', 'email')}{txt('url', 'Site')}
        {txt('contacto_nome', 'Nome de contacto')}<Field label="Gestor de conta" hint={souGestorConta ? 'Fica sempre consigo' : undefined}>{(id) => (
          <select id={id} className="inp" value={souGestorConta ? String(session.user()?.id) : f.gestor_conta_id} disabled={souGestorConta}
            onChange={(e) => setF({ ...f, gestor_conta_id: e.target.value })}>
            <option value="">Sem gestor de conta</option>
            {gestores.data?.map((g) => <option key={g.id} value={g.id}>{g.nome}</option>)}
            {cliente?.gestor_conta && !gestores.data?.some((g) => g.id === cliente.gestor_conta!.id) && <option value={cliente.gestor_conta.id}>{cliente.gestor_conta.nome} (inativo)</option>}
          </select>)}</Field>
        <div className="col-span-3">
          <Field label="Marcas" hint="Escreva o nome e carregue em Enter. Retirar uma marca não a apaga: deixa de estar disponível em contratos novos.">{(id) => (
            <div className="flex gap-2">
              <input id={id} className="inp flex-1" value={novaMarca} placeholder="Nova marca" onChange={(e) => setNovaMarca(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); juntarMarca() } }} />
              <Button icon="plus" disabled={!novaMarca.trim()} onClick={juntarMarca}>Acrescentar</Button>
            </div>)}</Field>
          <div className="flex flex-wrap gap-1.5 mt-2" aria-label="Marcas do cliente">
            {marcas.map((nome) => (
              <span key={nome} className="inline-flex items-center gap-1 h-7 pl-2.5 pr-1 rounded-full bg-ok-bg text-ok-fg text-[13px] font-medium">
                {nome}
                <button type="button" aria-label={`Retirar a marca ${nome}`} title={`Retirar a marca ${nome}`} onClick={() => setMarcas(marcas.filter((x) => x !== nome))}
                  className="grid place-items-center w-5 h-5 rounded-full hover:bg-[#C9E6D5]"><Icon name="x" size={12} /></button>
              </span>
            ))}
            {marcas.length === 0 && <span className="text-[12.5px] text-ink-60">Sem marcas</span>}
          </div>
        </div>
        <Field label="Observações" className="col-span-3">{(id) => <textarea id={id} className="inp h-20 py-2" value={f.observacoes} onChange={set('observacoes')} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

// ------------------------------------------------------------------ lojas
type Servico = { linha_id: number; contrato_id: number; contrato_numero: string; tipo: TipoContrato; estado: string; cliente: string; horas_semana: number; dias: string[]; colaborador: string | null }

function Lojas() {
  const [q, setQ] = useState('')
  const [inativos, setInativos] = useState(false)
  const [zona, setZona] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const [edit, setEdit] = useState<Loja | null>(null)
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const lista = useQuery({ queryKey: ['lojas', 'gestao', q, inativos, zona], queryFn: () => api<Loja[]>('/lojas', { params: { q, inativos, zona_id: zona } }) })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const itens = lista.data ?? []
  const atual = itens.find((l) => l.id === sel) ?? itens[0]
  const servicos = useQuery({ queryKey: ['loja-servicos', atual?.id], enabled: !!atual, queryFn: () => api<Servico[]>(`/lojas/${atual!.id}/servicos`) })
  const nomeSup = (id: number | null) => sups.data?.find((s) => s.id === id)?.nome ?? '—'
  return (
    <div className="flex flex-wrap items-start gap-4">
      <Card className="flex-[999_1_560px] overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-3.5 py-3 border-b border-line-soft">
          <Pesquisa value={q} onChange={setQ} placeholder="Nome, código ERP ou localidade" />
          <label className="inline-flex items-center gap-1.5 h-8 pl-2.5 pr-1 rounded-md border border-line-strong bg-white text-[13px] text-ink-80">Zona:
            <select value={zona} onChange={(e) => setZona(e.target.value)} className="bg-transparent font-medium text-ink outline-none"><option value="">Todas</option>{zonas.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}</select>
          </label>
          <MostrarInativos value={inativos} onChange={setInativos} />
          <span className="flex-1" /><span className="text-[12.5px] text-ink-60">{itens.length} lojas</span>
        </div>
        {lista.isLoading ? <Loading /> : lista.error ? <div className="p-4"><ErrorBox error={lista.error} /></div> : itens.length === 0 ? <Empty title="Sem lojas" /> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Loja</th><th>Insígnia</th><th>Zona</th><th>Supervisor</th><th>Horário</th></tr></thead>
              <tbody>{itens.map((l) => (
                <tr key={l.id} className={`${atual?.id === l.id ? '[&>td]:!bg-[#EAF4F2]' : ''} ${l.ativo ? '' : 'opacity-60'}`}>
                  <td><div className="flex items-center gap-2.5">
                    <InsigniaLogo id={l.insignia?.id} v={l.insignia?.logo_v} nome={l.insignia?.nome} size={26} inicial />
                    <div><NomeLink nome={l.nome} ativo={l.ativo} onClick={() => setSel(l.id)} />
                      <div className="text-xs text-ink-60">{[l.codigo_erp && `ERP ${l.codigo_erp}`, l.morada, l.localidade].filter(Boolean).join(' · ') || '—'}</div></div>
                  </div></td>
                  <td>{l.insignia?.nome ?? '—'}</td><td>{l.zona?.nome ?? '—'}</td>
                  <td className="text-[12.5px]">{nomeSup(l.supervisor_id)}</td>
                  <td className="text-[12.5px] text-ink-60">{l.horario_semana ?? '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
      {atual && (
        <Card className="flex-[0_1_400px] min-w-[320px]">
          <div className="flex gap-3.5 items-start p-[18px]">
            {atual.insignia?.logo_v ? <InsigniaLogo id={atual.insignia.id} v={atual.insignia.logo_v} nome={atual.insignia.nome} size={52} />
              : <span className="grid place-items-center w-[52px] h-[52px] rounded-xl bg-log-bg text-log-fg flex-none"><Icon name="store" size={24} /></span>}
            <div className="flex-1 min-w-0">
              <div className="text-[17px] font-semibold tracking-[-0.01em]">{atual.nome}</div>
              <div className="text-[12.5px] text-ink-60">{[atual.insignia?.nome, atual.zona && `Zona ${atual.zona.nome}`].filter(Boolean).join(' · ') || '—'}</div>
              <div className="flex gap-1.5 mt-2">{atual.ativo ? <Badge tone="ok" dot>Ativa</Badge> : <Badge dot>Inativa</Badge>}</div>
            </div>
            <Button size="sm" variant="primary" icon="edit" onClick={() => setEdit(atual)}>Editar</Button>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-[18px] py-3.5 border-t border-line-soft">
            <div className="col-span-2"><Facto k="Morada" v={[atual.morada, [atual.codigo_postal, atual.localidade].filter(Boolean).join(' ')].filter(Boolean).join(', ')} /></div>
            <Facto k="Código ERP" v={atual.codigo_erp} />
            <Facto k="Nome para credencial" v={atual.nome_credencial} />
            <Facto k="Supervisor da agência" v={nomeSup(atual.supervisor_id)} />
            <Facto k="Horário (semana)" v={atual.horario_semana} />
            <Facto k="Horário (fim de semana)" v={atual.horario_fim_semana} />
            <Facto k="Contacto na loja" v={[atual.contacto_nome, atual.contacto_funcao].filter(Boolean).join(' · ')} />
            <Facto k="Telefone" v={atual.contacto_telefone} href={atual.contacto_telefone ? `tel:${atual.contacto_telefone}` : undefined} />
            <div className="col-span-2"><Facto k="Email" v={atual.contacto_email} href={atual.contacto_email ? `mailto:${atual.contacto_email}` : undefined} /></div>
          </dl>
          <div className="px-[18px] py-3.5 border-t border-line-soft">
            <div className="text-[13px] font-semibold mb-2">Serviços em vigor</div>
            <ul className="flex flex-col gap-2.5">
              {servicos.data?.map((s) => (
                <li key={s.linha_id} className="text-[13px]">
                  <div className="flex items-center gap-2"><span className="font-medium">{s.cliente}</span><AreaBadge tipo={s.tipo} /><span className="flex-1" /><span className="num">{horas(s.horas_semana)}/sem</span></div>
                  <div className="text-xs text-ink-60"><Link to={`/contratos/${s.contrato_id}`} className="font-mono text-petrol-600 hover:underline">{s.contrato_numero}</Link> · {s.dias.join(', ')} · {s.colaborador ?? <span className="text-err-fg">por atribuir</span>}</div>
                </li>
              ))}
              {servicos.data?.length === 0 && <li className="text-[12.5px] text-ink-60">Sem serviços em vigor</li>}
            </ul>
          </div>
          <div className="flex justify-end px-[18px] py-3 border-t border-line-soft">
            <BotaoEstado url={`/lojas/${atual.id}/estado`} ativo={atual.ativo} nome={atual.nome} invalidar={['lojas']} />
          </div>
        </Card>
      )}
      {edit && <LojaDialog loja={edit} onClose={() => setEdit(null)} />}
    </div>
  )
}

function LojaDialog({ loja, onClose }: { loja?: Loja; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const ins = useQuery({ queryKey: ['insignias'], queryFn: () => api<IdNome[]>('/insignias') })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const campos = ['nome', 'codigo_erp', 'nome_credencial', 'morada', 'codigo_postal', 'localidade', 'horario_semana', 'horario_fim_semana', 'contacto_nome', 'contacto_funcao', 'contacto_email', 'contacto_telefone'] as const
  const [f, setF] = useState<Record<string, string>>(() => {
    const o: Record<string, string> = { insignia_id: String(loja?.insignia_id ?? ''), zona_id: String(loja?.zona_id ?? ''), supervisor_id: String(loja?.supervisor_id ?? '') }
    campos.forEach((k) => { o[k] = (loja?.[k] as string | null) ?? '' })
    return o
  })
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })
  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {}
      campos.forEach((k) => { body[k] = f[k].trim() || null })
      body.nome = f.nome.trim()
      ;(['insignia_id', 'zona_id', 'supervisor_id'] as const).forEach((k) => { body[k] = f[k] ? Number(f[k]) : null })
      return api(loja ? `/lojas/${loja.id}` : '/lojas', { method: loja ? 'PUT' : 'POST', body })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['lojas'] }); toast(loja ? 'Loja atualizada' : 'Loja criada'); onClose() },
  })
  const txt = (k: string, label: string, cls = '') => <Field label={label} className={cls}>{(id) => <input id={id} className="inp" value={f[k]} onChange={set(k)} />}</Field>
  const sel = (k: string, label: string, opts?: IdNome[]) => <Field label={label}>{(id) => <select id={id} className="inp" value={f[k]} onChange={set(k)}><option value="">—</option>{opts?.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}</select>}</Field>
  return (
    <Modal title={loja ? `Editar ${loja.nome}` : 'Nova loja'} onClose={onClose} width={680}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome.trim()} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-3 gap-3.5">
        {txt('nome', 'Nome do ponto de venda', 'col-span-2')}{txt('codigo_erp', 'Código ERP')}
        {txt('nome_credencial', 'Nome para credencial', 'col-span-2')}{sel('insignia_id', 'Insígnia', ins.data)}
        {sel('zona_id', 'Zona', zonas.data)}
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
