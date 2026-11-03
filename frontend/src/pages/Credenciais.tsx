import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { ColaboradorPicker } from '../components/ColaboradorPicker'
import { api, apiForm, descarregar, session } from '../lib/api'
import { dataCurta, iso } from '../lib/format'
import type { CredencialT, EstadoCredencial, IdNome, ModeloCredencialT, PrepararCredencial } from '../lib/types'

const ESTADO: Record<EstadoCredencial, { label: string; tone: 'ok' | 'neu' | 'err' }> = {
  emitida: { label: 'Em vigor', tone: 'ok' }, substituida: { label: 'Substituída', tone: 'neu' }, anulada: { label: 'Anulada', tone: 'err' },
}
const perfil = () => session.user()?.perfil ?? ''
export const podeEmitir = () => ['administrador', 'gestor', 'gestor_conta', 'rh', 'supervisor'].includes(perfil())
const podeModelos = () => ['administrador', 'gestor', 'gestor_conta', 'rh'].includes(perfil())
const baixar = (c: CredencialT) => descarregar(`/credenciais/${c.id}/ficheiro`, c.ficheiro_nome)

type Af = { linha_id: number; loja: string; cliente: string; contrato_numero: string }

// ------------------------------------------------------------------ emissão
/** Diálogo de emissão. Depois de uma afetação pergunta se é nova ou por substituição (ou "agora não"). */
export function EmitirCredencialDialog({ colaboradorId, linhaId, aposAfetacao, onClose }: {
  colaboradorId: number; linhaId: number; aposAfetacao?: boolean; onClose: () => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({
    queryKey: ['credencial-preparar', colaboradorId, linhaId],
    queryFn: () => api<PrepararCredencial>('/credenciais/preparar', { params: { colaborador_id: colaboradorId, linha_id: linhaId } }),
  })
  const [modo, setModo] = useState<'nova' | 'substituicao' | null>(null)
  const [f, setF] = useState<{ validade: string; exame: string; modelo: string; substitui: string; motivo: string } | null>(null)
  const p = q.data
  if (p && f === null) {
    setF({ validade: p.validade, exame: p.data_exame_medico ?? '', modelo: p.modelo ? String(p.modelo.id) : '', substitui: p.substituiveis[0] ? String(p.substituiveis[0].id) : '', motivo: '' })
    setModo(p.substituiveis.length ? 'substituicao' : 'nova')
  }
  const m = useMutation({
    mutationFn: () => api<CredencialT & { desconhecidos: string[] }>('/credenciais', { method: 'POST', body: {
      colaborador_id: colaboradorId, linha_id: linhaId, modelo_id: f!.modelo ? Number(f!.modelo) : null,
      valida_ate: f!.validade || null, data_exame_medico: f!.exame || null,
      substitui_id: modo === 'substituicao' && f!.substitui ? Number(f!.substitui) : null, motivo: f!.motivo || null,
    } }),
    onSuccess: async (c) => {
      qc.invalidateQueries({ queryKey: ['credenciais'] })
      toast(`Credencial ${c.numero} emitida${c.substitui ? ` (substitui ${c.substitui})` : ''}`)
      if (c.desconhecidos.length) toast(`O modelo tem campos que a plataforma não conhece: ${c.desconhecidos.join(', ')}`, 'warn')
      await baixar(c).catch(() => {})
      onClose()
    },
  })
  const subs = p?.substituiveis ?? []
  const validadeErr = f?.validade && f.validade < iso(new Date()) ? 'A validade não pode ser no passado' : null
  return (
    <Modal title={aposAfetacao ? 'Emitir credencial para a loja?' : 'Emitir credencial'} onClose={onClose} width={600}
      footer={<>
        <Button variant="ghost" onClick={onClose}>{aposAfetacao ? 'Agora não' : 'Cancelar'}</Button>
        <Button variant="primary" icon="file" loading={m.isPending} disabled={!p?.modelo || !f || !!validadeErr || (modo === 'substituicao' && !f.substitui)}
          onClick={() => m.mutate()}>{modo === 'substituicao' ? 'Emitir por substituição' : 'Emitir credencial nova'}</Button>
      </>}>
      {q.isLoading || !p || !f ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg bg-bg px-3.5 py-2.5 text-[13px]">
            <b className="font-semibold">{p.colaborador}</b> em <b className="font-semibold">{p.loja}</b>
            <span className="text-ink-60"> · {p.cliente} · {p.contrato}</span>
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="lbl mb-1.5">Tipo de emissão</legend>
            <label className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 cursor-pointer ${modo === 'nova' ? 'border-petrol-600 bg-petrol-50' : 'border-line'}`}>
              <input type="radio" name="modo" className="mt-0.5 accent-petrol-600" checked={modo === 'nova'} onChange={() => setModo('nova')} />
              <span><b className="font-medium text-[13.5px]">Credencial nova</b><span className="block text-[12.5px] text-ink-60">As credenciais em vigor nesta loja mantêm-se.</span></span>
            </label>
            <label className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 ${subs.length ? 'cursor-pointer' : 'opacity-50'} ${modo === 'substituicao' ? 'border-petrol-600 bg-petrol-50' : 'border-line'}`}>
              <input type="radio" name="modo" className="mt-0.5 accent-petrol-600" disabled={!subs.length} checked={modo === 'substituicao'} onChange={() => setModo('substituicao')} />
              <span className="flex-1"><b className="font-medium text-[13.5px]">Por substituição</b>
                <span className="block text-[12.5px] text-ink-60">{subs.length ? 'A credencial escolhida passa a «Substituída» e a nova indica qual substitui.' : 'Não há credenciais em vigor nesta loja para substituir.'}</span>
                {modo === 'substituicao' && subs.length > 0 && (
                  <select aria-label="Credencial a substituir" className="inp mt-2" value={f.substitui} onChange={(e) => setF({ ...f, substitui: e.target.value })}>
                    {subs.map((c) => <option key={c.id} value={c.id}>{c.numero} · {c.colaborador} · válida até {dataCurta(c.valida_ate)}</option>)}
                  </select>
                )}
              </span>
            </label>
          </fieldset>
          <div className="grid grid-cols-2 gap-3.5">
            <Field label="Válida até" error={validadeErr}>{(id) => <DataInput id={id} invalid={!!validadeErr} value={f.validade} min={iso(new Date())} onChange={(v) => setF({ ...f, validade: v })} />}</Field>
            <Field label="Data do exame médico" hint={p.data_exame_medico ? 'Da ficha de aptidão registada' : 'Sem ficha de aptidão registada'}>{(id) => <DataInput id={id} limpar value={f.exame} onChange={(v) => setF({ ...f, exame: v })} />}</Field>
            {p.modelos.length > 1 && (
              <Field label="Modelo" className="col-span-2">{(id) => (
                <select id={id} className="inp" value={f.modelo} onChange={(e) => setF({ ...f, modelo: e.target.value })}>
                  {p.modelos.map((x) => <option key={x.id} value={x.id}>{x.nome} (v{x.versao}){x.cliente ? ' · deste cliente' : ''}</option>)}
                </select>)}</Field>
            )}
            <Field label="Observação (opcional)" className="col-span-2">{(id) => <input id={id} className="inp" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} placeholder="Ex.: substituição por férias" />}</Field>
          </div>
          {p.aviso_modelo && <div className="rounded-lg bg-err-bg text-err-fg px-3.5 py-2.5 text-[13px]">{p.aviso_modelo}</div>}
          {p.modelo && <div className="text-xs text-ink-60">Modelo: {p.modelo.nome} (versão {p.modelo.versao}). O documento Word é descarregado depois de emitir e fica guardado na ficha do colaborador.</div>}
          {p.em_falta.length > 0 && (
            <div className="rounded-lg bg-warn-bg text-warn-fg px-3.5 py-2.5 text-[13px] flex gap-2">
              <Icon name="alert" size={16} className="mt-0.5 flex-none" />
              <span>Estes campos vão sair em branco: {p.em_falta.join(', ')}. Pode emitir na mesma ou completar primeiro a ficha do colaborador ou os Parâmetros.</span>
            </div>
          )}
          {m.error ? <ErrorBox error={m.error} /> : null}
        </div>
      )}
    </Modal>
  )
}

/** Escolher colaborador e loja (a partir das lojas afetas) antes de emitir. */
function NovaCredencialDialog({ colaborador: inicial, onClose }: { colaborador?: { id: number; nome: string }; onClose: () => void }) {
  const [colab, setColab] = useState<{ id: number; nome: string } | null>(inicial ?? null)
  const [linha, setLinha] = useState('')
  const [emitir, setEmitir] = useState(false)
  const afs = useQuery({ queryKey: ['colaborador-afetacoes', colab?.id], queryFn: () => api<Af[]>(`/colaboradores/${colab!.id}/afetacoes`), enabled: !!colab })
  if (emitir && colab && linha) return <EmitirCredencialDialog colaboradorId={colab.id} linhaId={Number(linha)} onClose={onClose} />
  return (
    <Modal title="Emitir credencial" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" disabled={!colab || !linha} onClick={() => setEmitir(true)}>Continuar</Button></>}>
      <div className="flex flex-col gap-3.5">
        {!inicial && <Field label="Colaborador">{(id) => <ColaboradorPicker id={id} value={colab} onChange={(c) => { setColab(c ? { id: c.id, nome: c.nome } : null); setLinha('') }} />}</Field>}
        {colab && (
          <Field label="Loja" hint="Lojas em que o colaborador está afeto">{(id) => (
            afs.isLoading ? <Loading /> : !afs.data?.length ? <div className="text-[13px] text-ink-60">O colaborador não está afeto a nenhuma loja.</div> : (
              <select id={id} className="inp" value={linha} onChange={(e) => setLinha(e.target.value)}>
                <option value="">Escolher…</option>
                {afs.data.map((a) => <option key={a.linha_id} value={a.linha_id}>{a.loja} · {a.cliente} · {a.contrato_numero}</option>)}
              </select>))}</Field>
        )}
      </div>
    </Modal>
  )
}

function AnularDialog({ c, onClose }: { c: CredencialT; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [motivo, setMotivo] = useState('')
  const m = useMutation({
    mutationFn: () => api(`/credenciais/${c.id}/anular`, { method: 'POST', body: { motivo } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['credenciais'] }); toast(`Credencial ${c.numero} anulada`, 'warn'); onClose() },
  })
  return (
    <Modal title={`Anular ${c.numero}`} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="danger" loading={m.isPending} disabled={motivo.trim().length < 3} onClick={() => m.mutate()}>Anular credencial</Button></>}>
      <p className="text-[13px] text-ink-60 mb-3">{c.colaborador} · {c.loja}. A credencial fica no histórico como anulada.</p>
      <Field label="Motivo">{(id) => <input id={id} className="inp" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}</Field>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}

function TabelaCredenciais({ itens, colaborador = true }: { itens: CredencialT[]; colaborador?: boolean }) {
  const [anular, setAnular] = useState<CredencialT | null>(null)
  const toast = useToast()
  const hoje = iso(new Date())
  return (
    <>
      <div className="overflow-x-auto">
        <table className="tbl">
          <thead><tr><th>N.º</th>{colaborador && <th>Colaborador</th>}<th>Loja</th><th>Emitida</th><th>Válida até</th><th>Estado</th><th>Modelo</th><th /></tr></thead>
          <tbody>{itens.map((c) => {
            const caducada = c.estado === 'emitida' && !!c.valida_ate && c.valida_ate < hoje
            return (
              <tr key={c.id} className={c.estado === 'emitida' ? '' : '[&>td]:!bg-[#F4F5F2] text-ink-60'}>
                <td className="num font-medium whitespace-nowrap">{c.numero}{c.substitui && <div className="text-xs text-ink-60 font-normal">substitui {c.substitui}</div>}</td>
                {colaborador && <td><div className="font-medium">{c.colaborador}</div><div className="text-xs text-ink-60">N.º {c.colaborador_numero}</div></td>}
                <td><div>{c.loja}</div><div className="text-xs text-ink-60">{c.cliente}</div></td>
                <td className="num text-[12.5px]">{dataCurta(c.emitida_em)}</td>
                <td className="num text-[12.5px]">{dataCurta(c.valida_ate)}</td>
                <td>{caducada ? <Badge tone="err" dot>Caducada</Badge> : <Badge tone={ESTADO[c.estado].tone} dot>{ESTADO[c.estado].label}</Badge>}
                  {c.motivo && <div className="text-xs text-ink-60 mt-0.5 max-w-[180px] truncate" title={c.motivo}>{c.motivo}</div>}</td>
                <td className="text-[12.5px] text-ink-60">{c.modelo}</td>
                <td className="text-right whitespace-nowrap">
                  <Button size="sm" variant="ghost" icon="file" onClick={() => baixar(c).catch((e) => toast(e.message, 'err'))}>Word</Button>
                  {c.estado === 'emitida' && podeEmitir() && <Button size="sm" variant="ghost" onClick={() => setAnular(c)}>Anular</Button>}
                </td>
              </tr>
            )
          })}</tbody>
        </table>
      </div>
      {anular && <AnularDialog c={anular} onClose={() => setAnular(null)} />}
    </>
  )
}

// ------------------------------------------------------------------ separador Credenciais
export function Credenciais() {
  const [estado, setEstado] = useState('emitida')
  const [texto, setTexto] = useState('')
  const [nova, setNova] = useState(false)
  const q = useQuery({ queryKey: ['credenciais'], queryFn: () => api<CredencialT[]>('/credenciais') })
  const itens = useMemo(() => {
    const t = texto.trim().toLowerCase()
    return (q.data ?? []).filter((c) => (!estado || c.estado === estado)
      && (!t || [c.numero, c.colaborador, c.colaborador_numero, c.loja, c.cliente].some((x) => x.toLowerCase().includes(t))))
  }, [q.data, estado, texto])
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2.5 px-[18px] py-3 border-b border-line-soft">
        <div className="relative w-[280px]">
          <Icon name="search" size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-60" />
          <input aria-label="Pesquisar credenciais" className="inp !pl-8" placeholder="N.º, colaborador, loja ou cliente" value={texto} onChange={(e) => setTexto(e.target.value)} />
        </div>
        <label className="inline-flex items-center gap-2 h-9 pl-3 pr-1 rounded-lg border border-line-strong text-[13px] text-ink-80">Mostrar
          <select aria-label="Estado" className="bg-transparent font-medium text-ink outline-none" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="emitida">Em vigor</option><option value="">Todas</option><option value="substituida">Substituídas</option><option value="anulada">Anuladas</option>
          </select>
        </label>
        <span className="flex-1" />
        <span className="text-[12.5px] text-ink-60">{itens.length} credenciais</span>
        {podeEmitir() && <Button size="sm" variant="primary" icon="plus" onClick={() => setNova(true)}>Emitir credencial</Button>}
      </div>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : !itens.length
        ? <Empty title="Sem credenciais">As credenciais são emitidas ao afetar um colaborador a uma loja, ou aqui.</Empty>
        : <TabelaCredenciais itens={itens} />}
      {nova && <NovaCredencialDialog onClose={() => setNova(false)} />}
    </Card>
  )
}

/** Secção da ficha do colaborador. */
export function CredenciaisColaborador({ id, nome }: { id: number; nome: string }) {
  const [nova, setNova] = useState(false)
  const q = useQuery({ queryKey: ['credenciais', 'colaborador', id], queryFn: () => api<CredencialT[]>('/credenciais', { params: { colaborador_id: id } }) })
  const vigor = (q.data ?? []).filter((c) => c.estado === 'emitida')
  return (
    <div className="px-[18px] py-3.5 border-t border-line-soft">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-[13px] font-semibold">Credenciais</div>
        <span className="text-[12.5px] text-ink-60">{vigor.length} em vigor</span>
        <span className="flex-1" />
        {podeEmitir() && <Button size="sm" icon="plus" onClick={() => setNova(true)}>Emitir</Button>}
      </div>
      {!q.data?.length ? <div className="text-[12.5px] text-ink-60">Sem credenciais emitidas.</div> : (
        <ul className="flex flex-col gap-1.5">
          {q.data.slice(0, 6).map((c) => (
            <li key={c.id} className={`flex items-center gap-2 text-[13px] ${c.estado === 'emitida' ? '' : 'text-ink-60'}`}>
              <span className="num font-medium">{c.numero}</span>
              <span className="truncate">{c.loja}</span>
              <span className="flex-1" />
              <span className="text-xs num">{c.estado === 'emitida' ? `até ${dataCurta(c.valida_ate)}` : ESTADO[c.estado].label}</span>
              <button type="button" aria-label={`Descarregar ${c.numero}`} onClick={() => baixar(c)} className="p-1 text-ink-60 hover:text-ink"><Icon name="file" size={15} /></button>
            </li>
          ))}
        </ul>
      )}
      {nova && <NovaCredencialDialog colaborador={{ id, nome }} onClose={() => setNova(false)} />}
    </div>
  )
}

// ------------------------------------------------------------------ separador Modelos
type Analise = { campos: string[]; desconhecidos: string[] }
type CampoT = { chave: string; descricao: string; grupo: string; marcador: string }

export function ModelosCredencial() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['modelos-credencial'], queryFn: () => api<ModeloCredencialT[]>('/modelos-credencial') })
  const campos = useQuery({ queryKey: ['credencial-campos'], queryFn: () => api<CampoT[]>('/credenciais/campos') })
  const [carregar, setCarregar] = useState<{ nome?: string; cliente_id?: number | null } | null>(null)
  const [verVersoes, setVerVersoes] = useState<string | null>(null)
  const grupos = useMemo(() => {
    const g = new Map<string, ModeloCredencialT[]>()
    for (const m of q.data ?? []) {
      const k = `${m.nome}|${m.cliente_id ?? ''}`
      g.set(k, [...(g.get(k) ?? []), m])
    }
    return [...g.entries()]
  }, [q.data])
  const estado = useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) => api(`/modelos-credencial/${id}/estado`, { method: 'POST', body: { ativo } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['modelos-credencial'] }),
  })
  const repor = useMutation({
    mutationFn: (id: number) => api<{ versao: number }>(`/modelos-credencial/${id}/repor`, { method: 'POST' }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['modelos-credencial'] }); toast(`Versão reposta como v${r.versao}`) },
  })
  const pode = podeModelos()
  const porGrupo = useMemo(() => {
    const g = new Map<string, CampoT[]>()
    for (const c of campos.data ?? []) g.set(c.grupo, [...(g.get(c.grupo) ?? []), c])
    return [...g.entries()]
  }, [campos.data])

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4 items-start">
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 px-[18px] py-3 border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Modelos de credencial</h3>
          <span className="text-[12.5px] text-ink-60">documentos Word com campos que a plataforma preenche</span>
          <span className="flex-1" />
          {pode && <Button size="sm" variant="primary" icon="plus" onClick={() => setCarregar({})}>Novo modelo</Button>}
        </div>
        {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : !grupos.length ? <Empty title="Sem modelos">Carregue um documento Word com os campos da credencial.</Empty> : (
          <table className="tbl">
            <thead><tr><th>Modelo</th><th>Versão em uso</th><th>Atualizado</th><th>Estado</th><th /></tr></thead>
            <tbody>{grupos.map(([k, vs]) => {
              const atual = vs.find((v) => v.atual) ?? vs[0]
              const aberto = verVersoes === k
              return [
                <tr key={k} className={atual.ativo ? '' : 'opacity-60'}>
                  <td><div className="font-medium">{atual.nome}</div><div className="text-xs text-ink-60">{atual.cliente ? `Só para ${atual.cliente}` : 'Todos os clientes'}{atual.notas ? ` · ${atual.notas}` : ''}</div></td>
                  <td className="num">v{atual.versao}{vs.length > 1 && <button type="button" className="ml-2 text-[12.5px] text-petrol-600 hover:underline" onClick={() => setVerVersoes(aberto ? null : k)}>{aberto ? 'esconder' : `${vs.length} versões`}</button>}</td>
                  <td className="text-[12.5px] text-ink-60">{dataCurta(atual.criado_em?.slice(0, 10) ?? null)}{atual.criado_por ? ` · ${atual.criado_por}` : ''}</td>
                  <td>{atual.ativo ? <Badge tone="ok" dot>Ativo</Badge> : <Badge dot>Inativo</Badge>}</td>
                  <td className="text-right whitespace-nowrap">
                    <Button size="sm" variant="ghost" icon="file" onClick={() => descarregar(`/modelos-credencial/${atual.id}/ficheiro`)}>Descarregar</Button>
                    {pode && <Button size="sm" variant="ghost" onClick={() => setCarregar({ nome: atual.nome, cliente_id: atual.cliente_id })}>Nova versão</Button>}
                    {pode && <Button size="sm" variant="ghost" onClick={() => estado.mutate({ id: atual.id, ativo: !atual.ativo })}>{atual.ativo ? 'Desativar' : 'Reativar'}</Button>}
                  </td>
                </tr>,
                ...(aberto ? vs.filter((v) => !v.atual).map((v) => (
                  <tr key={v.id} className="[&>td]:!bg-[#F7F8F6] text-[12.5px]">
                    <td className="pl-8 text-ink-60">{v.ficheiro_nome}{v.notas ? ` · ${v.notas}` : ''}</td>
                    <td className="num">v{v.versao}</td>
                    <td className="text-ink-60">{dataCurta(v.criado_em?.slice(0, 10) ?? null)}{v.criado_por ? ` · ${v.criado_por}` : ''}</td>
                    <td><Badge>Anterior</Badge></td>
                    <td className="text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" icon="file" onClick={() => descarregar(`/modelos-credencial/${v.id}/ficheiro`)}>Descarregar</Button>
                      {pode && <Button size="sm" variant="ghost" loading={repor.isPending} onClick={() => repor.mutate(v.id)}>Repor esta versão</Button>}
                    </td>
                  </tr>
                )) : []),
              ]
            })}</tbody>
          </table>
        )}
        <div className="px-[18px] py-3 border-t border-line-soft text-[12.5px] text-ink-60 flex gap-1.5">
          <Icon name="alert" size={14} className="mt-0.5 flex-none" />
          Para alterar o modelo: descarregue-o, edite no Word (texto, imagens, logótipo) e carregue-o como nova versão. As credenciais já emitidas guardam a versão com que foram feitas.
        </div>
      </Card>
      <Card className="overflow-hidden">
        <div className="px-[18px] py-3 border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Campos disponíveis</h3>
          <p className="text-[12.5px] text-ink-60 mt-0.5">Escreva no Word o marcador, por exemplo <code className="text-ink">{'{{nome}}'}</code>. Os campos de impressão em série (MERGEFIELD) do modelo antigo também funcionam.</p>
        </div>
        <div className="max-h-[560px] overflow-y-auto px-[18px] py-2">
          {porGrupo.map(([g, cs]) => (
            <div key={g} className="py-2">
              <div className="text-xs font-semibold text-ink-60 uppercase tracking-wide mb-1">{g}</div>
              {cs.map((c) => (
                <button key={c.chave} type="button" title="Copiar marcador" onClick={() => { navigator.clipboard?.writeText(c.marcador); toast(`${c.marcador} copiado`) }}
                  className="w-full text-left flex items-baseline gap-2 py-1 px-1.5 -mx-1.5 rounded hover:bg-bg">
                  <code className="text-[12px] text-petrol-600 whitespace-nowrap">{c.marcador}</code>
                  <span className="text-[12.5px] text-ink-60 truncate">{c.descricao}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </Card>
      {carregar && <CarregarModeloDialog base={carregar} onClose={() => setCarregar(null)} />}
    </div>
  )
}

function CarregarModeloDialog({ base, onClose }: { base: { nome?: string; cliente_id?: number | null }; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const versao = !!base.nome
  const [f, setF] = useState({ nome: base.nome ?? '', cliente_id: base.cliente_id ? String(base.cliente_id) : '', notas: '' })
  const [ficheiro, setFicheiro] = useState<File | null>(null)
  const [analise, setAnalise] = useState<(Analise & { versao: number }) | null>(null)
  const clientes = useQuery({ queryKey: ['clientes'], queryFn: () => api<IdNome[]>('/clientes'), enabled: !versao })
  const m = useMutation({
    mutationFn: () => apiForm<ModeloCredencialT & Analise>('/modelos-credencial', 'POST', { nome: f.nome.trim(), cliente_id: f.cliente_id, notas: f.notas, ficheiro }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['modelos-credencial'] })
      toast(`${r.nome}: versão ${r.versao} guardada`)
      if (r.desconhecidos.length) setAnalise({ ...r, versao: r.versao })
      else onClose()
    },
  })
  if (analise) {
    return (
      <Modal title="Modelo guardado, com campos desconhecidos" onClose={onClose} footer={<Button variant="primary" onClick={onClose}>Fechar</Button>}>
        <p className="text-[13px] mb-2">A versão {analise.versao} ficou guardada. Reconheci {analise.campos.length} campos, mas estes não existem na plataforma e vão ficar como estão no documento:</p>
        <ul className="list-disc pl-5 text-[13px] text-warn-fg">{analise.desconhecidos.map((d) => <li key={d}><code>{d}</code></li>)}</ul>
        <p className="text-[12.5px] text-ink-60 mt-3">Corrija-os no Word com os nomes da lista «Campos disponíveis» e carregue uma nova versão.</p>
      </Modal>
    )
  }
  return (
    <Modal title={versao ? `Nova versão · ${base.nome}` : 'Novo modelo de credencial'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome.trim() || !ficheiro} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="flex flex-col gap-3.5">
        {!versao && <>
          <Field label="Nome do modelo">{(id) => <input id={id} className="inp" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} placeholder="Ex.: Credencial padrão" />}</Field>
          <Field label="Cliente" hint="Só se este cliente tiver um modelo próprio">{(id) => (
            <select id={id} className="inp" value={f.cliente_id} onChange={(e) => setF({ ...f, cliente_id: e.target.value })}>
              <option value="">Todos os clientes</option>{clientes.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>)}</Field>
        </>}
        <Field label="Documento Word (.docx)">{(id) => (
          <input id={id} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="text-[13px]"
            onChange={(e) => setFicheiro(e.target.files?.[0] ?? null)} />)}</Field>
        <Field label="O que mudou (opcional)">{(id) => <input id={id} className="inp" value={f.notas} onChange={(e) => setF({ ...f, notas: e.target.value })} />}</Field>
        {m.error ? <ErrorBox error={m.error} /> : null}
      </div>
    </Modal>
  )
}
