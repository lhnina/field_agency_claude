import type { TipoContrato, Vinculo } from './types'

const nf = (d: number) => new Intl.NumberFormat('pt-PT', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: 'always' })

export const eur = (v: number | string, d = 2) => `${nf(d).format(Number(v))} €`
export const num = (v: number | string, d = 1) => nf(d).format(Number(v))
export const horas = (v: number | string) => `${nf(Number(v) % 1 === 0 ? 0 : 1).format(Number(v))} h`

export function parseISO(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}
export function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }
export const segunda = (d: Date) => addDays(d, -((d.getDay() + 6) % 7))

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const DIAS_CURTOS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
export const dataCurta = (s: string | null) => {
  if (!s) return '—'
  const d = parseISO(s)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}
export const diaMes = (s: string) => { const d = parseISO(s); return `${d.getDate()} ${MESES[d.getMonth()]}` }
export const diaSemana = (s: string) => DIAS_CURTOS[parseISO(s).getDay()]
export const intervaloSemana = (ini: string, fim: string) => {
  const a = parseISO(ini), b = parseISO(fim)
  return a.getMonth() === b.getMonth()
    ? `${a.getDate()} a ${b.getDate()} de ${MESES[b.getMonth()]} ${b.getFullYear()}`
    : `${a.getDate()} ${MESES[a.getMonth()]} a ${b.getDate()} ${MESES[b.getMonth()]} ${b.getFullYear()}`
}
export const semanaISO = (s: string) => {
  const d = parseISO(s)
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day = t.getUTCDay() || 7
  t.setUTCDate(t.getUTCDate() + 4 - day)
  const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  return Math.ceil(((t.getTime() - y0.getTime()) / 86400000 + 1) / 7)
}

export const VINCULO: Record<Vinculo, { label: string; tone: Tone }> = {
  sem_termo: { label: 'Sem termo', tone: 'neu' },
  a_termo: { label: 'A termo', tone: 'info' },
  muito_curta_duracao: { label: 'Muito curta duração', tone: 'warn' },
  recibos_verdes: { label: 'Recibos verdes', tone: 'neu' },
}
export const AREA: Record<TipoContrato, { label: string; cls: string; sq: string }> = {
  REP: { label: 'Reposição', cls: 'bg-rep-bg text-rep-fg', sq: 'bg-rep' },
  PRO: { label: 'Promoções', cls: 'bg-pro-bg text-pro-fg', sq: 'bg-pro' },
  LOG: { label: 'Logística', cls: 'bg-log-bg text-log-fg', sq: 'bg-log' },
  EQF: { label: 'Equipas Fixas', cls: 'bg-eqf-bg text-eqf-fg', sq: 'bg-eqf' },
}
export const ESTADO_CONTRATO: Record<string, { label: string; tone: Tone }> = {
  proposta: { label: 'Proposta', tone: 'info' },
  ativo: { label: 'Ativo', tone: 'ok' },
  suspenso: { label: 'Suspenso', tone: 'neu' },
  terminado: { label: 'Terminado', tone: 'neu' },
}
export type Tone = 'ok' | 'warn' | 'err' | 'info' | 'neu'

export const iniciais = (nome: string) => nome.split(/\s+/).filter(Boolean).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
