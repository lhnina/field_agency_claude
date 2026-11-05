import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon, Spinner, type IconName } from './ui'

const LIMITE = 30

type Props<T extends { id: number }> = {
  id?: string
  /** Chave de cache e função que pesquisa no servidor (recebe o termo e o limite). */
  chave: string
  pesquisar: (termo: string, limite: number) => Promise<T[]>
  value: { id: number; nome: string } | null
  onChange: (item: T | null) => void
  render: (item: T) => ReactNode
  icon: IconName
  placeholder: string
  /** Ordena os resultados (ex.: os da mesma zona primeiro). */
  ordenar?: (a: T, b: T) => number
}

/** Campo de escolha por pesquisa: escreve-se parte do nome e escolhe-se da lista (teclado ou rato). */
export function Pesquisa<T extends { id: number }>({ id, chave, pesquisar, value, onChange, render, icon, placeholder, ordenar }: Props<T>) {
  const [texto, setTexto] = useState('')
  const [termo, setTermo] = useState('')
  const [aberto, setAberto] = useState(false)
  const [ativo, setAtivo] = useState(0)
  const lista = useId()
  const caixa = useRef<HTMLDivElement>(null)

  useEffect(() => { const t = setTimeout(() => setTermo(texto.trim()), 200); return () => clearTimeout(t) }, [texto])
  useEffect(() => {
    const fora = (e: MouseEvent) => { if (!caixa.current?.contains(e.target as Node)) setAberto(false) }
    document.addEventListener('mousedown', fora); return () => document.removeEventListener('mousedown', fora)
  }, [])

  // A lista é posicionada em relação à janela, para não ficar cortada dentro de diálogos pequenos.
  const [pos, setPos] = useState<{ top?: number; bottom?: number; left: number; width: number } | null>(null)
  useEffect(() => {
    if (!aberto) return
    const calcular = () => {
      const el = caixa.current?.getBoundingClientRect()
      if (!el) return
      const abaixo = window.innerHeight - el.bottom
      setPos(abaixo < 300 && el.top > abaixo
        ? { bottom: window.innerHeight - el.top + 4, left: el.left, width: el.width }
        : { top: el.bottom + 4, left: el.left, width: el.width })
    }
    calcular()
    window.addEventListener('resize', calcular); window.addEventListener('scroll', calcular, true)
    return () => { window.removeEventListener('resize', calcular); window.removeEventListener('scroll', calcular, true) }
  }, [aberto])

  const r = useQuery({ queryKey: [chave, 'pesquisa', termo], queryFn: () => pesquisar(termo, LIMITE), enabled: aberto && termo.length >= 2 })
  const itens = ordenar ? [...(r.data ?? [])].sort(ordenar) : (r.data ?? [])

  function escolher(x: T) { onChange(x); setTexto(''); setTermo(''); setAberto(false) }

  if (value) {
    return (
      <div className="inp flex items-center gap-2">
        <Icon name={icon} size={16} className="text-ink-60 flex-none" />
        <span className="flex-1 truncate font-medium">{value.nome}</span>
        <button type="button" className="text-[12.5px] text-petrol-600 hover:underline" onClick={() => onChange(null)}>Alterar</button>
      </div>
    )
  }

  return (
    <div ref={caixa} className="relative">
      <div className="relative">
        <Icon name="search" size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-60" />
        <input id={id} className="inp !pl-8" autoComplete="off" placeholder={placeholder}
          role="combobox" aria-expanded={aberto} aria-controls={lista} aria-autocomplete="list"
          aria-activedescendant={aberto && itens[ativo] ? `${lista}-${itens[ativo].id}` : undefined}
          value={texto}
          onChange={(e) => { setTexto(e.target.value); setAberto(true); setAtivo(0) }}
          onFocus={() => setAberto(true)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setAberto(true); setAtivo((a) => Math.min(a + 1, itens.length - 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setAtivo((a) => Math.max(a - 1, 0)) }
            else if (e.key === 'Enter' && aberto && itens[ativo]) { e.preventDefault(); escolher(itens[ativo]) }
            else if (e.key === 'Escape') { if (aberto) e.stopPropagation(); setAberto(false) }
          }} />
      </div>
      {aberto && (
        <div id={lista} role="listbox" style={pos ?? undefined} className="fixed z-[60] max-h-72 overflow-y-auto bg-white border border-line rounded-lg shadow-lg py-1">
          {termo.length < 2 ? <div className="px-3 py-2 text-[12.5px] text-ink-60">Escreva pelo menos 2 letras para pesquisar.</div>
            : r.isFetching && !r.data ? <div className="px-3 py-2"><Spinner /></div>
            : itens.length === 0 ? <div className="px-3 py-2 text-[12.5px] text-ink-60">Sem resultados.</div>
            : itens.map((x, i) => (
              <div key={x.id} id={`${lista}-${x.id}`} role="option" aria-selected={i === ativo}
                onMouseDown={(e) => { e.preventDefault(); escolher(x) }} onMouseEnter={() => setAtivo(i)}
                className={`px-3 py-1.5 cursor-pointer ${i === ativo ? 'bg-petrol-50' : ''}`}>{render(x)}</div>
            ))}
          {itens.length === LIMITE && <div className="px-3 py-1.5 text-[11.5px] text-ink-60 border-t border-line-soft">A mostrar os primeiros {LIMITE} — refine a pesquisa.</div>}
        </div>
      )}
    </div>
  )
}
