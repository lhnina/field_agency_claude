import { Fragment, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FechoPeriodo, MesInput, mesAnterior, nomeMes } from '../components/Periodo'
import { Badge, Card, Empty, ErrorBox, Icon, Kpi, Loading, PageHeader, Seg } from '../components/ui'
import { api } from '../lib/api'
import { eur, horas, num } from '../lib/format'

type Tot = { horas_contratadas: number; valor: number; horas_executadas: number; custo: number; pendentes: number }
type LinhaPF = { linha_id: number; loja: string; dias_vigencia: number; dias_mes: number; horas_semana: number; preco_hora: number; horas_contratadas: number; valor: number; horas_executadas: number; custo: number; margem: number; pendentes_validacao: number }
type PF = {
  mes: string; area: string; fechado: boolean
  clientes: { cliente_id: number; cliente: string; codigo_erp: number | null; totais: Tot; contratos: { id: number; numero: string; evento: string | null; descricao: string | null; totais: Tot; linhas: LinhaPF[] }[] }[]
  totais: Tot & { margem: number; margem_pct: number }
}

const pct = (v: number, c: number) => (v ? ((v - c) / v) * 100 : 0)

export default function PreFaturacao() {
  const qc = useQueryClient()
  const [mes, setMes] = useState(mesAnterior())
  const [area, setArea] = useState('REP')
  const [aberto, setAberto] = useState<Set<number>>(new Set())
  const q = useQuery({ queryKey: ['prefaturacao', mes, area], queryFn: () => api<PF>('/prefaturacao', { params: { mes, area } }) })
  const d = q.data
  const toggle = (id: number) => setAberto((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  return (
    <>
      <PageHeader crumb="Financeiro" title="Pré-faturação"
        sub={area === 'REP' ? 'Reposição: faturada pelas horas contratadas (h/semana × 52 ÷ 12 × preço), em proporção dos dias de vigência no mês. As lojas sem colaborador também são faturadas.'
          : area === 'LOG' ? 'Logística: faturada pelo preço de cada serviço executado no mês. Os serviços por executar aparecem para controlo, sem valor.'
          : 'Promoções: faturadas pelas horas planeadas da campanha no mês. As lojas sem colaborador também são faturadas.'}>
        <Seg label="Área" value={area} onChange={setArea} options={[{ value: 'REP', label: 'Reposição' }, { value: 'PRO', label: 'Promoções' }, { value: 'LOG', label: 'Logística' }]} />
        <MesInput value={mes} onChange={setMes} />
        {d && <FechoPeriodo tipo="faturacao" mes={mes} area={area} fechado={d.fechado} onDone={() => qc.invalidateQueries({ queryKey: ['prefaturacao'] })}
          descricao={`Fecha a pré-faturação de ${area === 'REP' ? 'Reposição' : area === 'LOG' ? 'Logística' : 'Promoções'} de ${nomeMes(mes)} com ${eur(d.totais.valor ?? 0)}.`} />}
      </PageHeader>
      {q.isLoading ? <Card><Loading /></Card> : q.error || !d ? <ErrorBox error={q.error} /> : area === 'LOG' ? <PreFatLog d={d as unknown as PFLog} mes={mes} /> : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Kpi label={`A faturar · ${nomeMes(mes)}`} value={eur(d.totais.valor ?? 0)} sub={`${d.clientes.length} clientes`} />
            <Kpi label="Horas contratadas" value={horas(Math.round((d.totais.horas_contratadas ?? 0) * 10) / 10)} sub={`executadas ${horas(Math.round((d.totais.horas_executadas ?? 0) * 10) / 10)}`} />
            <Kpi label="Custo de mão de obra" value={eur(d.totais.custo ?? 0)} sub="executadas × custo/hora + encargos" />
            <Kpi label="Margem bruta" value={<span className={d.totais.margem_pct < 20 ? 'text-warn-fg' : 'text-ok-fg'}>{num(d.totais.margem_pct ?? 0)} %</span>} sub={eur(d.totais.margem ?? 0)} />
          </div>
          {(d.totais.pendentes ?? 0) > 0 && (
            <div className="rounded-lg bg-warn-bg text-[#6B4000] px-3.5 py-2.5 text-[13px] flex items-center gap-2">
              <Icon name="alert" size={16} />{d.totais.pendentes} serviços deste mês ainda por validar. O valor a faturar não muda, mas o custo e a margem ainda podem mudar.
            </div>
          )}
          <Card className="overflow-hidden">
            <div className="flex items-center gap-2 px-[18px] py-3 border-b border-line-soft text-[12.5px] text-ink-60">
              <Icon name="receipt" size={16} />Nesta fase a pré-faturação é só para consulta. O envio para o ERP, como dossier interno BO/BI com detalhe por loja, chega numa fase seguinte.
            </div>
            {d.clientes.length === 0 ? <Empty title="Sem serviços a faturar neste mês" /> : (
              <div className="overflow-x-auto">
                <table className="tbl">
                  <thead><tr><th>Cliente · contrato · loja</th><th className="text-right">Dias</th><th className="text-right">H/semana</th><th className="text-right">Contratadas</th><th className="text-right">Preço/h</th><th className="text-right">A faturar</th><th className="text-right">Executadas</th><th className="text-right">Custo</th><th className="text-right">Margem</th></tr></thead>
                  <tbody>
                    {d.clientes.map((c) => (
                      <Fragment key={c.cliente_id}>
                        <tr className="cursor-pointer [&>td]:bg-[#FAFBF9] [&>td]:font-medium" onClick={() => toggle(c.cliente_id)}>
                          <td><button type="button" aria-expanded={aberto.has(c.cliente_id)} className="flex items-center gap-2 font-semibold">
                            <Icon name={aberto.has(c.cliente_id) ? 'cd' : 'cr'} size={15} />{c.cliente}</button>
                            <span className="text-xs text-ink-60 font-normal ml-6">{c.contratos.length} contrato{c.contratos.length > 1 ? 's' : ''}{c.codigo_erp ? ` · ERP ${c.codigo_erp}` : ''}</span></td>
                          <td /><td />
                          <td className="text-right num">{num(c.totais.horas_contratadas)}</td><td />
                          <td className="text-right num font-semibold">{eur(c.totais.valor)}</td>
                          <td className="text-right num">{num(c.totais.horas_executadas)}</td>
                          <td className="text-right num">{eur(c.totais.custo)}</td>
                          <td className="text-right num"><Margem v={pct(c.totais.valor, c.totais.custo)} /></td>
                        </tr>
                        {aberto.has(c.cliente_id) && c.contratos.map((ct) => (
                          <Fragment key={ct.id}>
                            <tr><td colSpan={9} className="!py-1.5 !pl-9 text-xs text-ink-60"><span className="font-mono">{ct.numero}</span> · {ct.evento ?? ct.descricao}
                              {ct.totais.pendentes > 0 && <Badge tone="warn" className="ml-2">{ct.totais.pendentes} por validar</Badge>}</td></tr>
                            {ct.linhas.map((l) => (
                              <tr key={l.linha_id}>
                                <td className="!pl-9">{l.loja}{l.horas_executadas === 0 && l.horas_contratadas > 0 &&
                                  <Badge tone="err" className="ml-2" >sem execução</Badge>}</td>
                                <td className={`text-right num ${l.dias_vigencia < l.dias_mes ? 'text-warn-fg font-medium' : 'text-ink-60'}`} title={l.dias_vigencia < l.dias_mes ? 'Linha com vigência parcial no mês' : undefined}>{l.dias_vigencia}/{l.dias_mes}</td>
                                <td className="text-right num">{area === 'REP' ? num(l.horas_semana) : '—'}</td>
                                <td className="text-right num">{num(l.horas_contratadas)}</td>
                                <td className="text-right num">{eur(l.preco_hora)}</td>
                                <td className="text-right num">{eur(l.valor)}</td>
                                <td className="text-right num">{num(l.horas_executadas)}</td>
                                <td className="text-right num">{eur(l.custo)}</td>
                                <td className="text-right num"><Margem v={pct(l.valor, l.custo)} /></td>
                              </tr>
                            ))}
                          </Fragment>
                        ))}
                      </Fragment>
                    ))}
                  </tbody>
                  <tfoot><tr className="[&>td]:border-t [&>td]:border-line [&>td]:font-semibold">
                    <td className="px-3 py-3">Total</td><td /><td />
                    <td className="text-right num px-3">{num(d.totais.horas_contratadas)}</td><td />
                    <td className="text-right num px-3">{eur(d.totais.valor)}</td>
                    <td className="text-right num px-3">{num(d.totais.horas_executadas)}</td>
                    <td className="text-right num px-3">{eur(d.totais.custo)}</td>
                    <td className="text-right num px-3"><Margem v={d.totais.margem_pct} /></td>
                  </tr></tfoot>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}

function Margem({ v }: { v: number }) {
  return <span className={`font-medium ${v < 15 ? 'text-err-fg' : v < 20 ? 'text-warn-fg' : 'text-ok-fg'}`}>{num(v)} %</span>
}

// ------------------------------------------------------------------ logística
type LinhaLog = { linha_id: number; loja: string; data: string; tipo: string; estado: string; referencia_erp: string | null; preco: number; valor: number; custo: number; margem: number; km: number }
type TotLog = { valor: number; custo: number; km: number; pendentes: number; por_executar: number }
type PFLog = { clientes: { cliente_id: number; cliente: string; codigo_erp: number | null; totais: TotLog; contratos: { id: number; numero: string; descricao: string | null; totais: TotLog; linhas: LinhaLog[] }[] }[]; totais: TotLog & { margem: number; margem_pct: number } }
const ESTADO_PF: Record<string, { label: string; tone: 'ok' | 'warn' | 'err' | 'info' }> = {
  validado: { label: 'Validado', tone: 'ok' }, executado: { label: 'Por validar', tone: 'warn' }, atribuido: { label: 'Por executar', tone: 'info' }, planeado: { label: 'Por atribuir', tone: 'err' },
}

function PreFatLog({ d, mes }: { d: PFLog; mes: string }) {
  const t = d.totais
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Kpi label={`A faturar · ${nomeMes(mes)}`} value={eur(t.valor ?? 0)} sub={`${d.clientes.length} clientes`} />
        <Kpi label="Por executar ou validar" value={`${(t.por_executar ?? 0) + (t.pendentes ?? 0)}`} sub={`${t.por_executar ?? 0} por executar · ${t.pendentes ?? 0} por validar`} />
        <Kpi label="Custo de transporte e mão de obra" value={eur(t.custo ?? 0)} sub={`${num(t.km ?? 0, 0)} km`} />
        <Kpi label="Margem bruta" value={<span className={t.margem_pct < 20 ? 'text-warn-fg' : 'text-ok-fg'}>{num(t.margem_pct ?? 0)} %</span>} sub={eur(t.margem ?? 0)} />
      </div>
      {((t.por_executar ?? 0) + (t.pendentes ?? 0)) > 0 && (
        <div className="rounded-lg bg-warn-bg text-[#6B4000] px-3.5 py-2.5 text-[13px] flex items-center gap-2">
          <Icon name="alert" size={16} />Há serviços deste mês por registar ou por validar: só passam a faturar depois de executados, e o mês só fecha com todos validados.
        </div>
      )}
      <Card className="overflow-hidden">
        {d.clientes.length === 0 ? <Empty title="Sem serviços de logística neste mês" /> : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Cliente · contrato · serviço</th><th>Data</th><th>Estado</th><th>Ref. ERP</th><th className="text-right">Preço</th><th className="text-right">A faturar</th><th className="text-right">Km</th><th className="text-right">Custo</th><th className="text-right">Margem</th></tr></thead>
              <tbody>{d.clientes.map((c) => (
                <Fragment key={c.cliente_id}>
                  <tr className="[&>td]:bg-[#FAFBF9] [&>td]:font-medium">
                    <td className="font-semibold">{c.cliente}<span className="text-xs text-ink-60 font-normal ml-2">{c.codigo_erp ? `ERP ${c.codigo_erp}` : ''}</span></td>
                    <td /><td /><td /><td />
                    <td className="text-right num font-semibold">{eur(c.totais.valor)}</td>
                    <td className="text-right num">{num(c.totais.km, 0)}</td>
                    <td className="text-right num">{eur(c.totais.custo)}</td>
                    <td className="text-right num"><Margem v={pct(c.totais.valor, c.totais.custo)} /></td>
                  </tr>
                  {c.contratos.map((ct) => (
                    <Fragment key={ct.id}>
                      <tr><td colSpan={9} className="!py-1.5 !pl-6 text-xs text-ink-60"><span className="font-mono">{ct.numero}</span>{ct.descricao ? ` · ${ct.descricao}` : ''}</td></tr>
                      {ct.linhas.map((l) => (
                        <tr key={l.linha_id}>
                          <td className="!pl-9">{l.tipo} · {l.loja}</td>
                          <td className="num text-[12.5px]">{l.data.split('-').reverse().join('/')}</td>
                          <td><Badge tone={ESTADO_PF[l.estado]?.tone ?? 'info'} dot>{ESTADO_PF[l.estado]?.label ?? l.estado}</Badge></td>
                          <td className="text-[12.5px] text-ink-60">{l.referencia_erp ?? '—'}</td>
                          <td className="text-right num text-ink-60">{eur(l.preco)}</td>
                          <td className="text-right num">{eur(l.valor)}</td>
                          <td className="text-right num">{l.km ? num(l.km, 0) : '—'}</td>
                          <td className="text-right num">{l.custo ? eur(l.custo) : '—'}</td>
                          <td className="text-right num">{l.valor ? <Margem v={pct(l.valor, l.custo)} /> : '—'}</td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </Fragment>
              ))}</tbody>
              <tfoot><tr className="[&>td]:border-t [&>td]:border-line [&>td]:font-semibold">
                <td className="px-3 py-3">Total</td><td /><td /><td /><td />
                <td className="text-right num px-3">{eur(t.valor ?? 0)}</td>
                <td className="text-right num px-3">{num(t.km ?? 0, 0)}</td>
                <td className="text-right num px-3">{eur(t.custo ?? 0)}</td>
                <td className="text-right num px-3"><Margem v={t.margem_pct ?? 0} /></td>
              </tr></tfoot>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
