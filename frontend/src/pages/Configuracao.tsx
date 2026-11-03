import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, CardHeader, ErrorBox, Field, Loading, PageHeader, Seg, useToast } from '../components/ui'
import Utilizadores from './Utilizadores'
import Feriados from './Feriados'
import { api, session } from '../lib/api'
import { eur } from '../lib/format'
import { DataInput } from '../components/DataInput'

type Empresa = {
  nome: string; nif: string | null; morada: string | null; codigo_postal: string | null; localidade: string | null
  registo_comercial: string | null; seguradora: string | null; apolice: string | null; apolice_validade: string | null
}
type Cfg = {
  nome: string; pode_editar: boolean; empresa: Empresa; aceitacao_tacita: boolean; limite_margem_pct: string
  encargos_sem_termo_pct: string; encargos_a_termo_pct: string; encargos_muito_curta_pct: string; encargos_recibos_verdes_pct: string
}
const ENCARGOS: { k: keyof Cfg; label: string }[] = [
  { k: 'encargos_sem_termo_pct', label: 'Sem termo' }, { k: 'encargos_a_termo_pct', label: 'A termo' },
  { k: 'encargos_muito_curta_pct', label: 'Muito curta duração' }, { k: 'encargos_recibos_verdes_pct', label: 'Recibos verdes' },
]
const n = (v: string) => Number(String(v).replace(',', '.'))

/** Dados da empresa usados nas credenciais (nome, sede, registo, seguro de acidentes de trabalho). */
function EmpresaCard({ cfg, ro }: { cfg: Cfg; ro: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [e, setE] = useState<Empresa>(cfg.empresa)
  const m = useMutation({
    mutationFn: () => api<Cfg>('/configuracao/empresa', { method: 'PUT', body: Object.fromEntries(Object.entries(e).map(([k, v]) => [k, v === '' ? null : v])) }),
    onSuccess: (c) => { qc.setQueryData(['configuracao'], c); toast('Dados da empresa guardados') },
  })
  const txt = (k: keyof Empresa, label: string, cls = '') => (
    <Field label={label} className={cls}>{(id) => <input id={id} className="inp" disabled={ro} value={e[k] ?? ''} onChange={(ev) => setE({ ...e, [k]: ev.target.value })} />}</Field>
  )
  return (
    <Card>
      <CardHeader title="Empresa" meta="Dados que aparecem nas credenciais">
        {!ro && <Button size="sm" variant="primary" icon="check" loading={m.isPending} disabled={!e.nome.trim()} onClick={() => m.mutate()}>Guardar empresa</Button>}
      </CardHeader>
      <div className="p-[18px] grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-[1000px]">
        {txt('nome', 'Nome da empresa', 'col-span-2')}{txt('nif', 'NIF')}<span />
        {txt('morada', 'Sede (morada)', 'col-span-2')}{txt('codigo_postal', 'Código postal')}{txt('localidade', 'Localidade')}
        {txt('registo_comercial', 'Registo comercial', 'col-span-2 lg:col-span-4')}
        {txt('seguradora', 'Seguradora (acidentes de trabalho)', 'col-span-2')}{txt('apolice', 'N.º da apólice')}
        <Field label="Apólice válida até">{(id) => <DataInput id={id} limpar value={e.apolice_validade ?? ''} onChange={(v) => setE({ ...e, apolice_validade: v || null })} />}</Field>
      </div>
      {m.error ? <div className="px-[18px] pb-4"><ErrorBox error={m.error} /></div> : null}
    </Card>
  )
}

function Parametros() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['configuracao'], queryFn: () => api<Cfg>('/configuracao') })
  const [f, setF] = useState<Cfg | null>(null)
  useEffect(() => { if (q.data) setF({ ...q.data }) }, [q.data])
  const m = useMutation({
    mutationFn: (c: Cfg) => api<Cfg>('/configuracao', { method: 'PUT', body: {
      aceitacao_tacita: c.aceitacao_tacita, limite_margem_pct: n(c.limite_margem_pct),
      ...Object.fromEntries(ENCARGOS.map(({ k }) => [k, n(c[k] as string)])),
    } }),
    onSuccess: (c) => { qc.setQueryData(['configuracao'], c); qc.invalidateQueries({ queryKey: ['prefaturacao'] }); toast('Configuração guardada') },
  })
  if (q.isLoading || !f) return <Card><Loading /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  const ro = !f.pode_editar
  const invalido = ENCARGOS.some(({ k }) => Number.isNaN(n(f[k] as string)) || n(f[k] as string) < 0 || n(f[k] as string) > 200)
    || Number.isNaN(n(f.limite_margem_pct))
  const exemplo = 11.4

  return (
    <>
      {!ro && <div className="flex justify-end -mt-1"><Button variant="primary" icon="check" loading={m.isPending} disabled={invalido} onClick={() => m.mutate(f)}>Guardar parâmetros</Button></div>}
      {ro && <div className="rounded-lg bg-info-bg text-info-fg px-3.5 py-2.5 text-[13px]">Só a Direção ou o Administrador podem alterar estes parâmetros.</div>}
      {m.error ? <ErrorBox error={m.error} /> : null}
      <EmpresaCard cfg={f} ro={ro} />
      <Card>
        <CardHeader title="Encargos sociais sobre o custo/hora" meta="TSU, seguro de acidentes de trabalho, proporcionais de férias e subsídios" />
        <div className="p-[18px] flex flex-col gap-4">
          <p className="text-[13px] text-ink-60 max-w-[760px]">
            A percentagem soma-se ao custo/hora da ficha do colaborador para calcular custos e margens. O apuramento para salários continua com o valor que o colaborador recebe.
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-[900px]">
            {ENCARGOS.map(({ k, label }) => (
              <Field key={k} label={`${label} (%)`} hint={`${eur(exemplo)}/h → ${eur(exemplo * (1 + (n(f[k] as string) || 0) / 100))}/h`}>
                {(id) => <input id={id} inputMode="decimal" className="inp num" disabled={ro} value={String(f[k]).replace('.', ',')}
                  onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
              </Field>
            ))}
          </div>
        </div>
      </Card>
      <Card>
        <CardHeader title="Operação e controlo" />
        <div className="p-[18px] grid gap-5 max-w-[760px]">
          <label className="flex items-start gap-3 text-[13.5px]">
            <input type="checkbox" className="w-4 h-4 mt-0.5 accent-petrol-600" disabled={ro} checked={f.aceitacao_tacita} onChange={(e) => setF({ ...f, aceitacao_tacita: e.target.checked })} />
            <span><b className="font-medium">Aceitação tácita</b><span className="block text-[12.5px] text-ink-60">Os serviços passados sem registo do colaborador contam como executados, com as horas planeadas, também para remuneração.</span></span>
          </label>
          <Field label="Limite de margem para alerta (%)" className="max-w-[220px]">
            {(id) => <input id={id} inputMode="decimal" className="inp num" disabled={ro} value={String(f.limite_margem_pct).replace('.', ',')} onChange={(e) => setF({ ...f, limite_margem_pct: e.target.value })} />}
          </Field>
        </div>
      </Card>
    </>
  )
}

export default function Configuracao() {
  const gere = ['administrador', 'direcao'].includes(session.user()?.perfil ?? '')
  const [tab, setTab] = useState(gere ? 'utilizadores' : 'parametros')
  const opts = [...(gere ? [{ value: 'utilizadores', label: 'Utilizadores' }] : []), { value: 'feriados', label: 'Feriados' }, { value: 'parametros', label: 'Parâmetros' }]
  return (
    <>
      <PageHeader crumb="Configuração" title="Configuração da organização">
        <Seg label="Secção" value={tab} onChange={setTab} options={opts} />
      </PageHeader>
      {tab === 'utilizadores' ? <Utilizadores /> : tab === 'feriados' ? <Feriados /> : <Parametros />}
    </>
  )
}
