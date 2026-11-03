import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AreaBadge, Badge, Bar, Button, Card, CardHeader, Empty, ErrorBox, Icon, Kpi, Loading, PageHeader } from '../components/ui'
import { api, session } from '../lib/api'
import { dataCurta, diaMes, diaSemana, eur, horas } from '../lib/format'
import type { Ocorrencia, ResumoDoc } from '../lib/types'

type Dash = {
  faturacao_mensal_prevista: number; horas_contratadas_mes: number; horas_planeadas_mes: number; contratos_ativos: number
  contratos_a_terminar: { id: number; numero: string; fim: string }[]
  semana: { total: number; por_atribuir: number; conflitos: number; ausencias: number; horas: number }
  por_atribuir: Ocorrencia[]; alertas_colaboradores: { id: number; nome: string; alertas: string[] }[]
  documentacao?: ResumoDoc
}

export default function Dashboard() {
  const user = session.user()
  const q = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dash>('/dashboard/operacional') })
  const lg = useQuery({ queryKey: ['dashboard-logistica'], queryFn: () => api<{ proximos_7_dias: number; hoje: number; por_atribuir: number; com_alertas: number }>('/dashboard/logistica') })
  const hoje = new Date()
  if (q.isLoading) return <Card><Loading /></Card>
  if (q.error || !q.data) return <ErrorBox error={q.error} />
  const d = q.data
  const cobertura = d.horas_contratadas_mes ? (d.horas_planeadas_mes / d.horas_contratadas_mes) * 100 : 0
  return (
    <>
      <PageHeader title={`${hoje.getHours() < 13 ? 'Bom dia' : hoje.getHours() < 20 ? 'Boa tarde' : 'Boa noite'}, ${user?.nome.split(' ')[0] ?? ''}`}
        sub={hoje.toLocaleDateString('pt-PT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}>
        <Link to="/planeamento"><Button variant="primary" icon="cal">Abrir planeamento</Button></Link>
      </PageHeader>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Kpi label="Faturação mensal prevista" value={eur(d.faturacao_mensal_prevista, 0)} sub={`${d.contratos_ativos} contratos em curso · horas contratadas`} />
        <Kpi label="Horas contratadas · mês" value={horas(Math.round(d.horas_contratadas_mes))} sub="horas/semana × 52 ÷ 12" />
        <Kpi label="Horas planeadas · este mês" value={horas(Math.round(d.horas_planeadas_mes))}
          sub={`${Math.round(cobertura)} % das contratadas`} extra={<div className="mt-2"><Bar pct={cobertura} tone={cobertura < 95 ? 'warn' : 'ok'} /></div>} />
        <Kpi label="Esta semana" value={`${d.semana.total} turnos`} sub={<span className={d.semana.por_atribuir ? 'text-err-fg font-medium' : ''}>{d.semana.por_atribuir} por atribuir · {d.semana.conflitos} conflitos</span>} />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-4">
        <Card>
          <CardHeader title="Serviços por atribuir" meta="esta semana"><Link to="/planeamento" className="text-[13px] font-medium text-petrol-600 hover:underline">Planeamento</Link></CardHeader>
          {d.por_atribuir.length === 0 ? <Empty title="Todos os serviços da semana têm colaborador" /> : (
            <div className="overflow-x-auto px-1.5 pt-3 pb-1.5">
              <table className="tbl">
                <thead><tr><th>Dia</th><th>Loja</th><th>Cliente</th><th>Área</th><th className="text-right">Horas</th></tr></thead>
                <tbody>{d.por_atribuir.map((o) => (
                  <tr key={o.id}><td className="num">{diaSemana(o.data)} {diaMes(o.data)}</td><td className="font-medium">{o.loja}</td><td>{o.cliente}</td><td><AreaBadge tipo={o.tipo} /></td><td className="text-right num">{horas(o.horas)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Alertas operacionais" />
          <ul className="px-[18px] py-2">
            {d.documentacao && (d.documentacao.expirados + d.documentacao.em_falta > 0) && <Alerta tone="err" icon="shield"
              titulo={`Documentação: ${d.documentacao.expirados} expirados · ${d.documentacao.em_falta} em falta`}
              sub={`${d.documentacao.colaboradores_com_problemas} colaboradores · ${d.documentacao.a_expirar} a expirar em breve`} to="/documentacao" />}
            {d.documentacao && !(d.documentacao.expirados + d.documentacao.em_falta) && d.documentacao.a_expirar > 0 && <Alerta tone="warn" icon="shield"
              titulo={`${d.documentacao.a_expirar} documentos a expirar`} sub="Renovar antes da validade" to="/documentacao?estado=a_expirar" />}
            {lg.data && lg.data.proximos_7_dias > 0 && <Alerta tone={lg.data.por_atribuir ? 'err' : 'warn'} icon="truck"
              titulo={`Logística: ${lg.data.hoje} serviço${lg.data.hoje === 1 ? '' : 's'} hoje · ${lg.data.proximos_7_dias} nos próximos 7 dias`}
              sub={`${lg.data.por_atribuir} sem viatura ou motorista · ${lg.data.com_alertas} com alertas`} to="/logistica" />}
            {d.semana.ausencias > 0 && <Alerta tone="warn" icon="sun" titulo={`${d.semana.ausencias} ${d.semana.ausencias === 1 ? "ausência" : "ausências"} esta semana`} sub="Ver serviços por substituir" to="/ausencias" />}
            {d.alertas_colaboradores.map((c) => <Alerta key={c.id} tone="err" icon="alert" titulo={c.nome} sub={c.alertas.join(' · ')} to="/planeamento" />)}
            {d.contratos_a_terminar.map((c) => <Alerta key={c.id} tone="neu" icon="file" titulo={`${c.numero} termina`} sub={dataCurta(c.fim)} to={`/contratos/${c.id}`} />)}
            {!d.semana.ausencias && !d.alertas_colaboradores.length && !(d.documentacao && d.documentacao.expirados + d.documentacao.em_falta + d.documentacao.a_expirar) && !d.contratos_a_terminar.length && <li className="py-6 text-center text-ink-60 text-sm">Sem alertas.</li>}
          </ul>
        </Card>
      </div>
    </>
  )
}

function Alerta({ tone, icon, titulo, sub, to }: { tone: 'warn' | 'err' | 'neu'; icon: 'sun' | 'alert' | 'file' | 'shield' | 'truck'; titulo: string; sub: string; to: string }) {
  return (
    <li className="flex gap-3 items-start py-2.5 border-b border-line-soft last:border-0">
      <Badge tone={tone} className="!w-[30px] !h-[30px] !p-0 justify-center !rounded-lg"><Icon name={icon} size={16} /></Badge>
      <div className="flex-1 min-w-0"><div className="font-medium text-[13.5px]">{titulo}</div><div className="text-[12.5px] text-ink-60">{sub}</div></div>
      <Link to={to} className="text-[12.5px] font-medium text-petrol-600 hover:underline pt-0.5">Ver</Link>
    </li>
  )
}
