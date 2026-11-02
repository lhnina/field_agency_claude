import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FechoPeriodo, MesInput, mesAnterior, nomeMes } from '../components/Periodo'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Icon, Kpi, Loading, PageHeader, Seg, useToast } from '../components/ui'
import { api, session } from '../lib/api'
import { VINCULO, eur, horas, num } from '../lib/format'
import type { Vinculo } from '../lib/types'

type Ap = {
  mes: string; fechado: boolean
  colaboradores: { colaborador_id: number; numero: string; nome: string; vinculo: Vinculo; prestador: boolean; horas: number; valor: number; pendentes: number
    linhas: { cliente: string; codigo_phc: number | null; valor_hora: number; horas: number; valor: number; tacitas: number; servicos: number }[] }[]
  totais: { horas: number; valor: number; valor_trabalhadores: number; valor_prestadores: number; colaboradores: number; prestadores: number; pendentes: number }
}

export default function Apuramentos() {
  const qc = useQueryClient()
  const toast = useToast()
  const [mes, setMes] = useState(mesAnterior())
  const [filtro, setFiltro] = useState('todos')
  const [aberto, setAberto] = useState<Set<number>>(new Set())
  const q = useQuery({ queryKey: ['apuramento', mes], queryFn: () => api<Ap>('/apuramento', { params: { mes } }) })
  const d = q.data
  const lista = (d?.colaboradores ?? []).filter((c) => filtro === 'todos' || (filtro === 'prestadores' ? c.prestador : filtro === 'pendentes' ? c.pendentes > 0 : !c.prestador))
  const toggle = (id: number) => setAberto((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  async function exportar() {
    const r = await fetch(`/api/apuramento/export.csv?mes=${mes}`, { headers: { Authorization: `Bearer ${session.token()}` } })
    if (!r.ok) { toast('Não foi possível exportar', 'err'); return }
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement('a')
    a.href = url; a.download = `apuramento-${mes}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <PageHeader crumb="Financeiro" title="Apuramento de remunerações"
        sub="Horas validadas por colaborador e cliente, valorizadas ao custo/hora (ou ao custo especial da linha). Para processamento no PHC.">
        <MesInput value={mes} onChange={setMes} />
        <Button icon="receipt" onClick={exportar} disabled={!d?.colaboradores.length}>Exportar para o PHC (CSV)</Button>
        {d && <FechoPeriodo tipo="remuneracao" mes={mes} fechado={d.fechado} onDone={() => qc.invalidateQueries({ queryKey: ['apuramento'] })}
          bloqueio={d.totais.pendentes ? `${d.totais.pendentes} serviços por validar` : null}
          descricao={`Fecha o apuramento de ${nomeMes(mes)}: ${horas(d.totais.horas)} e ${eur(d.totais.valor)}.`} />}
      </PageHeader>
      {q.isLoading ? <Card><Loading /></Card> : q.error || !d ? <ErrorBox error={q.error} /> : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Kpi label="Horas validadas" value={horas(Math.round(d.totais.horas * 10) / 10)} sub={`${d.totais.colaboradores} trabalhadores · ${d.totais.prestadores} prestadores`} />
            <Kpi label="Trabalhadores" value={eur(d.totais.valor_trabalhadores)} sub="para processamento salarial" />
            <Kpi label="Prestadores (recibos verdes)" value={eur(d.totais.valor_prestadores)} sub="conferência de serviços a pagar" />
            <Kpi label="Por validar" value={<span className={d.totais.pendentes ? 'text-err-fg' : 'text-ok-fg'}>{d.totais.pendentes}</span>}
              sub={d.totais.pendentes ? <Link to="/validacao" className="text-petrol-600 font-medium hover:underline">Ir para a validação</Link> : 'pronto para fechar'} />
          </div>
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-2 px-3.5 py-3 border-b border-line-soft">
              <Seg label="Filtro" value={filtro} onChange={setFiltro} options={[{ value: 'todos', label: 'Todos' }, { value: 'trabalhadores', label: 'Trabalhadores' }, { value: 'prestadores', label: 'Prestadores' }, { value: 'pendentes', label: 'Com pendentes' }]} />
              <span className="flex-1" /><span className="text-[12.5px] text-ink-60">{lista.length} colaboradores</span>
            </div>
            {lista.length === 0 ? <Empty title="Sem horas validadas neste mês" /> : (
              <div className="overflow-x-auto">
                <table className="tbl">
                  <thead><tr><th>Colaborador</th><th>Vínculo</th><th className="text-right">Clientes</th><th className="text-right">Horas</th><th className="text-right">Valor</th><th>Situação</th></tr></thead>
                  <tbody>{lista.map((c) => (
                    <Fragment key={c.colaborador_id}>
                      <tr className="cursor-pointer" onClick={() => toggle(c.colaborador_id)}>
                        <td><button type="button" aria-expanded={aberto.has(c.colaborador_id)} className="flex items-center gap-2.5 text-left">
                          <Icon name={aberto.has(c.colaborador_id) ? 'cd' : 'cr'} size={15} className="text-ink-60" /><Avatar nome={c.nome} />
                          <span><span className="font-medium">{c.nome}</span><span className="block text-xs text-ink-60">N.º {c.numero}</span></span></button></td>
                        <td><Badge tone={VINCULO[c.vinculo].tone}>{VINCULO[c.vinculo].label}</Badge></td>
                        <td className="text-right num">{c.linhas.length}</td>
                        <td className="text-right num font-medium">{num(c.horas)}</td>
                        <td className="text-right num font-semibold">{eur(c.valor)}</td>
                        <td>{c.pendentes ? <Badge tone="err" dot>{c.pendentes} por validar</Badge> : <Badge tone="ok" dot>Validado</Badge>}</td>
                      </tr>
                      {aberto.has(c.colaborador_id) && c.linhas.map((l, i) => (
                        <tr key={i} className="[&>td]:bg-[#FAFBF9]">
                          <td className="!pl-[76px]">{l.cliente}<span className="block text-xs text-ink-60">{l.servicos} serviços{l.tacitas ? ` · ${l.tacitas} por aceitação tácita` : ''}{l.codigo_phc ? ` · PHC ${l.codigo_phc}` : ''}</span></td>
                          <td className="text-xs text-ink-60 num">{eur(l.valor_hora)}/h</td><td />
                          <td className="text-right num">{num(l.horas)}</td><td className="text-right num">{eur(l.valor)}</td><td />
                        </tr>
                      ))}
                    </Fragment>
                  ))}</tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}
