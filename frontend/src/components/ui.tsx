import { createContext, useCallback, useContext, useEffect, useId, useState } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { AREA, iniciais } from '../lib/format'
import type { Tone } from '../lib/format'
import type { TipoContrato } from '../lib/types'

// ------------------------------------------------------------------ ícones (traço 1,75, 24×24)
const PATHS = {
  dash: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  cal: 'M3 5h18v16H3zM3 10h18M8 3v4M16 3v4',
  'check-sq': 'M4 4h16v16H4zM8 12l3 3 5-6',
  'user-x': 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a7 7 0 0 1 11-5.7M17 15l5 5M22 15l-5 5',
  truck: 'M1 6h13v10H1zM14 10h4l4 4v2h-8zM6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  file: 'M6 2h9l5 5v15H6zM14 2v6h6M9 13h8M9 17h6',
  mega: 'M3 10v4h4l8 5V5L7 10zM18 9a4 4 0 0 1 0 6',
  store: 'M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a7 7 0 0 1 14 0v1M16 3.5a4 4 0 0 1 0 7.5M22 21v-1a7 7 0 0 0-4-6.3',
  shield: 'M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5zM9 12l2 2 4-4',
  trend: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  receipt: 'M5 2h14v20l-3-2-2 2-2-2-2 2-2-2-3 2zM9 7h6M9 11h6M9 15h4',
  calc: 'M5 2h14v20H5zM8 6h8v4H8zM8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01',
  sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
  bell: 'M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0',
  plus: 'M12 5v14M5 12h14',
  cl: 'M15 18l-6-6 6-6',
  cr: 'M9 18l6-6-6-6',
  cd: 'M6 9l6 6 6-6',
  alert: 'M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01',
  clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
  check: 'M20 6L9 17l-5-5',
  x: 'M18 6L6 18M6 6l12 12',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  swap: 'M7 7h13l-3-3M17 17H4l3 3',
  hist: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2',
  edit: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  logout: 'M9 21H5V3h4M16 17l5-5-5-5M21 12H9',
  sync: 'M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M3 21v-5h5',
  user: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21v-1a8 8 0 0 1 16 0v1',
  trash: 'M3 6h18M8 6V4h8v2M6 6l1 15h10l1-15M10 11v6M14 11v6',
  download: 'M12 3v12M7 10l5 5 5-5M4 21h16',
  route: 'M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM9 18h6.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H15',
} as const
export type IconName = keyof typeof PATHS

export function Icon({ name, size = 18, className = '', strokeWidth }: { name: IconName; size?: number; className?: string; strokeWidth?: number }) {
  const sw = strokeWidth ?? (name === 'more' ? 2.6 : 1.75)
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={sw}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={'flex-none ' + className}>
      <path d={PATHS[name]} />
    </svg>
  )
}

// ------------------------------------------------------------------ botões
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'subtil'; size?: 'sm' | 'md'; icon?: IconName; loading?: boolean }
export function Button({ variant = 'secondary', size = 'md', icon, loading, children, className = '', disabled, ...rest }: BtnProps) {
  const base = 'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium rounded-lg border transition-colors disabled:opacity-45 disabled:cursor-not-allowed'
  const sz = size === 'sm' ? 'h-[30px] px-2.5 text-[12.5px] rounded-md' : 'h-9 px-3.5 text-[13.5px]'
  const v = {
    primary: 'bg-petrol-600 border-petrol-600 text-white hover:bg-petrol-700',
    secondary: 'bg-white border-line-strong text-ink hover:bg-bg',
    ghost: 'bg-transparent border-transparent text-ink hover:bg-line-soft',
    danger: 'bg-transparent border-transparent text-err-fg hover:bg-err-bg',
    subtil: 'bg-petrol-50 border-petrol-100 text-petrol-700 hover:bg-petrol-100',
  }[variant]
  return (
    <button type="button" className={`${base} ${sz} ${v} ${className}`} disabled={disabled || loading} {...rest}>
      {loading ? <Spinner /> : icon ? <Icon name={icon} size={size === 'sm' ? 14 : 16} /> : null}
      {children}
    </button>
  )
}

export function IconButton({ icon, label, className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; label: string }) {
  return (
    <button type="button" aria-label={label} title={label}
      className={`grid place-items-center w-9 h-9 rounded-lg border border-line bg-white text-ink-80 hover:bg-bg ${className}`} {...rest}>
      <Icon name={icon} />
    </button>
  )
}

/** Ação de grelha só com ícone; o texto aparece ao passar o rato (e é lido pelos leitores de ecrã). */
export function AcaoIcone({ icon, label, tom = 'neutro', loading, className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: IconName; label: string; tom?: 'neutro' | 'perigo'; loading?: boolean
}) {
  return (
    <button type="button" aria-label={label} title={label} disabled={rest.disabled || loading}
      className={`inline-grid place-items-center w-8 h-8 rounded-lg align-middle disabled:opacity-45 ${tom === 'perigo' ? 'text-ink-60 hover:text-err-fg hover:bg-err-bg' : 'text-ink-60 hover:text-ink hover:bg-line-soft'} ${className}`} {...rest}>
      {loading ? <Spinner /> : <Icon name={icon} size={16} />}
    </button>
  )
}

/** Secção de cartão que abre e fecha: fica sempre visível a linha do título, o resumo e a ação. */
export function Seccao({ titulo, resumo, acao, children, abertaInicial = false }: {
  titulo: string; resumo?: ReactNode; acao?: ReactNode; children: ReactNode; abertaInicial?: boolean
}) {
  const [aberta, setAberta] = useState(abertaInicial)
  const id = useId()
  return (
    <div className="border-t border-line-soft">
      <div className="flex items-center gap-2 px-[18px] py-3">
        <button type="button" aria-expanded={aberta} aria-controls={id} onClick={() => setAberta(!aberta)}
          title={aberta ? 'Esconder o detalhe' : 'Mostrar o detalhe'} className="flex items-center gap-2 min-w-0 flex-1 text-left rounded -mx-1 px-1 hover:bg-bg">
          <Icon name="cr" size={14} className={`flex-none self-start mt-[3px] text-ink-60 transition-transform ${aberta ? 'rotate-90' : ''}`} />
          <span className="min-w-0 flex flex-col items-start gap-0.5">
            <span className="text-[13px] font-semibold">{titulo}</span>
            {resumo && <span className="max-w-full">{resumo}</span>}
          </span>
        </button>
        {acao}
      </div>
      {aberta && <div id={id} className="px-[18px] pb-3.5 -mt-1">{children}</div>}
    </div>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return <span className={`inline-block w-3.5 h-3.5 rounded-full border-2 border-current border-r-transparent animate-spin ${className}`} aria-hidden="true" />
}

// ------------------------------------------------------------------ indicadores
const TONES: Record<Tone, string> = {
  ok: 'bg-ok-bg text-ok-fg', warn: 'bg-warn-bg text-warn-fg', err: 'bg-err-bg text-err-fg', info: 'bg-info-bg text-info-fg', neu: 'bg-[#EDEFEC] text-ink-80',
}
export function Badge({ tone = 'neu', dot, children, className = '' }: { tone?: Tone; dot?: boolean; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full text-xs font-medium whitespace-nowrap ${TONES[tone]} ${className}`}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}{children}
    </span>
  )
}
export function AreaBadge({ tipo }: { tipo: TipoContrato }) {
  const a = AREA[tipo]
  return <span className={`inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full text-xs font-medium ${a.cls}`}><span className={`w-2 h-2 rounded-sm ${a.sq}`} />{a.label}</span>
}

export function Avatar({ nome, size = 28 }: { nome: string; size?: number; tone?: number }) {
  const tone = [...nome].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7)
  const cores = ['bg-[#CFE3DF] text-[#0F2B2A]', 'bg-[#F6DDC6] text-[#5C2A08]', 'bg-[#DCE4F7] text-[#1D3F80]', 'bg-[#E6E0F5] text-[#3D2F7A]', 'bg-[#F3E5B8] text-[#5A4300]']
  return (
    <span className={`grid place-items-center rounded-full font-semibold flex-none ${cores[tone % cores.length]}`}
      style={{ width: size, height: size, fontSize: size * 0.4 }} aria-hidden="true">{iniciais(nome)}</span>
  )
}

export function Bar({ pct, tone = 'ok' }: { pct: number; tone?: 'ok' | 'warn' | 'err' }) {
  const c = { ok: 'bg-petrol-600', warn: 'bg-warn', err: 'bg-err' }[tone]
  return <div className="h-1.5 rounded bg-[#E6E9E5] overflow-hidden min-w-[56px]"><div className={`h-full rounded ${c}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
}

// ------------------------------------------------------------------ estrutura
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card min-w-0 ${className}`}>{children}</section>
}
export function CardHeader({ title, meta, children }: { title: ReactNode; meta?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2.5 px-[18px] pt-4">
      <h3 className="text-[14.5px] font-semibold">{title}</h3>
      {meta && <span className="text-[12.5px] text-ink-60">{meta}</span>}
      <span className="flex-1" />
      {children}
    </div>
  )
}

export function PageHeader({ crumb, title, sub, children }: { crumb?: string; title: string; sub?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        {crumb && <div className="text-[12.5px] text-ink-60 mb-1">{crumb}</div>}
        <h1 className="text-2xl font-semibold tracking-[-0.02em] leading-tight">{title}</h1>
        {sub && <div className="text-[13.5px] text-ink-60 mt-0.5">{sub}</div>}
      </div>
      <span className="flex-1" />
      {children}
    </div>
  )
}

export function Seg<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex p-[3px] rounded-[10px] bg-[#E6E9E5] gap-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}
          className={`h-[30px] px-3 rounded-[7px] text-[13px] ${o.value === value ? 'bg-white text-ink font-medium shadow-seg' : 'text-ink-80 hover:text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Kpi({ label, value, sub, extra }: { label: string; value: ReactNode; sub?: ReactNode; extra?: ReactNode }) {
  return (
    <Card className="px-[18px] py-4">
      <div className="text-[12.5px] text-ink-60">{label}</div>
      <div className="text-[26px] font-semibold tracking-[-0.025em] mt-1.5 leading-tight num">{value}</div>
      {sub && <div className="text-[12.5px] text-ink-60 mt-1.5">{sub}</div>}
      {extra}
    </Card>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-6 py-12 text-center">
      <div className="font-medium">{title}</div>
      {children && <div className="text-[13px] text-ink-60 mt-1">{children}</div>}
    </div>
  )
}

export function Loading() {
  return <div className="flex items-center gap-2 text-ink-60 text-sm px-6 py-10"><Spinner /> A carregar…</div>
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div className="rounded-lg bg-err-bg text-err-fg px-3 py-2 text-[13px]">{error instanceof Error ? error.message : 'Ocorreu um erro'}</div>
}

// ------------------------------------------------------------------ formulários
export function Field({ label, error, hint, children, className = '' }: { label: string; error?: string | null; hint?: string; children: (id: string) => ReactNode; className?: string }) {
  const id = useId()
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="lbl">{label}</label>
      {children(id)}
      {error ? <span className="text-xs text-err-fg">{error}</span> : hint ? <span className="text-xs text-ink-60">{hint}</span> : null}
    </div>
  )
}

export function Modal({ title, onClose, children, footer, width = 560 }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; width?: number }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 bg-[#0F2B2A]/40 grid place-items-center p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div role="dialog" aria-modal="true" aria-label={title} className="bg-white rounded-xl shadow-pop w-full max-h-[90vh] flex flex-col" style={{ maxWidth: width }}>
        <div className="flex items-center gap-3 px-5 py-4 border-b border-line-soft">
          <h2 className="text-base font-semibold flex-1">{title}</h2>
          <button type="button" aria-label="Fechar" onClick={onClose} className="text-ink-60 hover:text-ink"><Icon name="x" /></button>
        </div>
        <div className="px-5 py-4 overflow-y-auto">{children}</div>
        {footer && <div className="flex justify-end gap-2 px-5 py-3 border-t border-line-soft bg-[#FAFBF9] rounded-b-xl">{footer}</div>}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ notificações
type ToastMsg = { id: number; tone: Tone; text: string }
const ToastCtx = createContext<(text: string, tone?: Tone) => void>(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastMsg[]>([])
  const push = useCallback((text: string, tone: Tone = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, tone, text }])
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`rounded-lg shadow-pop px-4 py-2.5 text-[13px] font-medium ${TONES[t.tone]}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
