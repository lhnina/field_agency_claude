import { useEffect, useRef, useState } from 'react'
import { Icon } from './ui'

// Seletores de data e de mês em português (os nativos do browser seguem a língua do browser).
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
const MESES_CURTOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const DIAS = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D']
const DIAS_NOME = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']

const pad = (n: number) => String(n).padStart(2, '0')
const isoDe = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`
const hojeIso = () => { const t = new Date(); return isoDe(t.getFullYear(), t.getMonth(), t.getDate()) }
const paraTexto = (v: string) => (v ? `${v.slice(8, 10)}/${v.slice(5, 7)}/${v.slice(0, 4)}` : '')

/** Converte "dd/mm/aaaa" (também d/m/aa, dd-mm-aaaa ou ddmmaaaa) para ISO; null se inválida. */
function deTexto(t: string): string | null {
  const s = t.trim()
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (iso) return deTexto(`${iso[3]}/${iso[2]}/${iso[1]}`)
  let m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/)
  if (!m && /^\d{8}$/.test(s)) m = ['', s.slice(0, 2), s.slice(2, 4), s.slice(4)] as unknown as RegExpMatchArray
  if (!m) return null
  const d = Number(m[1]), mes = Number(m[2]) - 1
  let y = Number(m[3]); if (y < 100) y += 2000
  const dt = new Date(y, mes, d)
  if (dt.getFullYear() !== y || dt.getMonth() !== mes || dt.getDate() !== d) return null
  return isoDe(y, mes, d)
}

function useFora(aberto: boolean, fechar: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!aberto) return
    const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) fechar() }
    document.addEventListener('mousedown', f); return () => document.removeEventListener('mousedown', f)
  }, [aberto, fechar])
  return ref
}

type Props = {
  id?: string
  value: string // ISO (aaaa-mm-dd) ou ''
  onChange: (v: string) => void
  min?: string
  max?: string
  invalid?: boolean
  className?: string
  /** Mostra o botão "Limpar" (campos opcionais). */
  limpar?: boolean
  disabled?: boolean
}

export function DataInput({ id, value, onChange, min, max, invalid, className = '', limpar, disabled }: Props) {
  const [texto, setTexto] = useState(paraTexto(value))
  const [aberto, setAberto] = useState(false)
  const [erro, setErro] = useState(false)
  const base = value || (min && hojeIso() < min ? min : max && hojeIso() > max ? max : hojeIso())
  const [vista, setVista] = useState({ y: Number(base.slice(0, 4)), m: Number(base.slice(5, 7)) - 1 })
  const ref = useFora(aberto, () => setAberto(false))
  // O calendário é posicionado em relação à janela, para não ficar cortado dentro de diálogos com scroll.
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 })

  useEffect(() => { setTexto(paraTexto(value)); setErro(false) }, [value])
  useEffect(() => {
    if (!aberto) return
    const fechar = (e: Event) => { if (!(e.target instanceof Node && ref.current?.contains(e.target))) setAberto(false) }
    window.addEventListener('scroll', fechar, true); window.addEventListener('resize', fechar)
    return () => { window.removeEventListener('scroll', fechar, true); window.removeEventListener('resize', fechar) }
  }, [aberto, ref])

  function abrir() {
    const b = value || base
    setVista({ y: Number(b.slice(0, 4)), m: Number(b.slice(5, 7)) - 1 })
    const r = ref.current?.getBoundingClientRect()
    if (r) {
      const alt = 330, larg = 264
      const top = r.bottom + 4 + alt > window.innerHeight && r.top - 4 - alt > 0 ? r.top - 4 - alt : r.bottom + 4
      setPos({ top, left: Math.max(8, Math.min(r.left, window.innerWidth - larg - 8)) })
    }
    setAberto(true)
  }
  function escolher(v: string) { onChange(v); setTexto(paraTexto(v)); setErro(false); setAberto(false) }
  function confirmarTexto() {
    if (!texto.trim()) { if (value) onChange(''); setErro(false); return }
    const v = deTexto(texto)
    if (v) { onChange(v); setTexto(paraTexto(v)); setErro(false) } else setErro(true)
  }
  const fora = (v: string) => (min && v < min) || (max && v > max)

  const primeiro = new Date(vista.y, vista.m, 1)
  const desloc = (primeiro.getDay() + 6) % 7 // segunda = 0
  const nDias = new Date(vista.y, vista.m + 1, 0).getDate()
  const celulas: (number | null)[] = [...Array(desloc).fill(null), ...Array.from({ length: nDias }, (_, i) => i + 1)]
  const hoje = hojeIso()
  const mudarMes = (n: number) => setVista(({ y, m }) => { const d = new Date(y, m + n, 1); return { y: d.getFullYear(), m: d.getMonth() } })

  return (
    <div ref={ref} className={`relative ${className}`}
      onKeyDown={(e) => { if (e.key === 'Escape' && aberto) { e.stopPropagation(); e.preventDefault(); setAberto(false) } }}>
      <input id={id} className={`inp num pr-9 ${invalid || erro ? 'inp-err' : ''}`} placeholder="dd/mm/aaaa" inputMode="numeric" autoComplete="off" disabled={disabled}
        value={texto} onBlur={confirmarTexto}
        onChange={(e) => {
          setTexto(e.target.value); setErro(false)
          const v = /^\d{1,2}\D\d{1,2}\D\d{4}$|^\d{4}-\d{2}-\d{2}$/.test(e.target.value.trim()) ? deTexto(e.target.value) : null
          if (v && v !== value) onChange(v) // data completa e válida: aplica logo
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); confirmarTexto() }
          else if (e.key === 'ArrowDown' && e.altKey) { e.preventDefault(); abrir() }
        }}
        aria-invalid={invalid || erro || undefined} title={erro ? 'Data inválida: use dd/mm/aaaa' : undefined} />
      <button type="button" aria-label="Abrir calendário" tabIndex={-1} disabled={disabled} onClick={() => (aberto ? setAberto(false) : abrir())}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-ink-60 hover:text-ink hover:bg-bg disabled:opacity-40 disabled:hover:bg-transparent"><Icon name="cal" size={16} /></button>
      {aberto && (
        <div role="dialog" aria-label="Calendário" style={{ top: pos.top, left: pos.left }} className="fixed z-[60] w-[264px] bg-white border border-line rounded-xl shadow-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <button type="button" aria-label="Mês anterior" onClick={() => mudarMes(-1)} className="p-1 rounded hover:bg-bg"><Icon name="cl" size={16} /></button>
            <div className="text-[13.5px] font-semibold capitalize">{MESES[vista.m]} {vista.y}</div>
            <button type="button" aria-label="Mês seguinte" onClick={() => mudarMes(1)} className="p-1 rounded hover:bg-bg"><Icon name="cr" size={16} /></button>
          </div>
          <div className="grid grid-cols-7 gap-0.5 text-center">
            {DIAS.map((d, i) => <div key={i} title={DIAS_NOME[i]} className="text-[11px] text-ink-60 py-1">{d}</div>)}
            {celulas.map((d, i) => {
              if (d === null) return <div key={`v${i}`} />
              const v = isoDe(vista.y, vista.m, d)
              const sel = v === value, desat = !!fora(v)
              return (
                <button key={v} type="button" disabled={desat} onClick={() => escolher(v)} aria-label={`${d} de ${MESES[vista.m]} de ${vista.y}`}
                  className={`h-8 rounded-md text-[13px] num ${sel ? 'bg-petrol-600 text-white font-semibold' : desat ? 'text-[#C3C9C5] cursor-not-allowed' : 'hover:bg-petrol-50'} ${v === hoje && !sel ? 'ring-1 ring-inset ring-petrol-600 text-petrol-600 font-semibold' : ''}`}>{d}</button>
              )
            })}
          </div>
          <div className="flex justify-between mt-2 pt-2 border-t border-line-soft text-[12.5px]">
            {limpar ? <button type="button" onClick={() => escolher('')} className="text-ink-60 hover:text-ink">Limpar</button> : <span />}
            <button type="button" disabled={!!fora(hoje)} onClick={() => escolher(hoje)} className="text-petrol-600 font-medium hover:underline disabled:text-ink-60 disabled:no-underline">Hoje</button>
          </div>
        </div>
      )}
    </div>
  )
}

/** Seletor de mês (aaaa-mm) em português. */
export function MesSeletor({ value, onChange, max }: { value: string; onChange: (v: string) => void; max?: string }) {
  const [aberto, setAberto] = useState(false)
  const [ano, setAno] = useState(Number(value.slice(0, 4)))
  const ref = useFora(aberto, () => setAberto(false))
  const m = Number(value.slice(5, 7)) - 1
  return (
    <div ref={ref} className="relative inline-block">
      <button type="button" onClick={() => { setAno(Number(value.slice(0, 4))); setAberto(!aberto) }}
        className="inline-flex items-center gap-1.5 font-medium text-ink capitalize">{MESES[m]} {value.slice(0, 4)}<Icon name="cd" size={14} className="text-ink-60" /></button>
      {aberto && (
        <div role="dialog" aria-label="Escolher mês" className="absolute z-40 mt-2 right-0 w-[232px] bg-white border border-line rounded-xl shadow-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <button type="button" aria-label="Ano anterior" onClick={() => setAno(ano - 1)} className="p-1 rounded hover:bg-bg"><Icon name="cl" size={16} /></button>
            <div className="text-[13.5px] font-semibold num">{ano}</div>
            <button type="button" aria-label="Ano seguinte" disabled={!!max && ano >= Number(max.slice(0, 4))} onClick={() => setAno(ano + 1)} className="p-1 rounded hover:bg-bg disabled:opacity-30"><Icon name="cr" size={16} /></button>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {MESES_CURTOS.map((nome, i) => {
              const v = `${ano}-${pad(i + 1)}`
              const desat = !!max && v > max
              return (
                <button key={v} type="button" disabled={desat} onClick={() => { onChange(v); setAberto(false) }}
                  className={`h-8 rounded-md text-[13px] capitalize ${v === value ? 'bg-petrol-600 text-white font-semibold' : desat ? 'text-[#C3C9C5]' : 'hover:bg-petrol-50'}`}>{nome}</button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
