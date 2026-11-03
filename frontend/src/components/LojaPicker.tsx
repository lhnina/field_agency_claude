import { useEffect, useId, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Loja } from '../lib/types'
import { Icon, Spinner } from './ui'

type Props = {
  id?: string
  value: { id: number; nome: string } | null
  onChange: (loja: Loja | null) => void
  /** Lojas que já existem no contrato: aparecem assinaladas. */
  usadas?: Set<number>
}

/** Escolha de loja por pesquisa (nome, localidade, código postal ou morada), adequada a milhares de lojas. */
export function LojaPicker({ id, value, onChange, usadas }: Props) {
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

  const r = useQuery({
    queryKey: ['lojas', 'pesquisa', termo],
    queryFn: () => api<Loja[]>(`/lojas?limite=30${termo ? `&q=${encodeURIComponent(termo)}` : ''}`),
    enabled: aberto && termo.length >= 2,
  })
  const itens = r.data ?? []

  function escolher(l: Loja) { onChange(l); setTexto(''); setTermo(''); setAberto(false) }

  if (value) {
    return (
      <div className="inp flex items-center gap-2">
        <Icon name="store" size={16} className="text-ink-60 flex-none" />
        <span className="flex-1 truncate font-medium">{value.nome}</span>
        <button type="button" className="text-[12.5px] text-petrol-600 hover:underline" onClick={() => onChange(null)}>Alterar</button>
      </div>
    )
  }

  return (
    <div ref={caixa} className="relative">
      <div className="relative">
        <Icon name="search" size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-60" />
        <input id={id} className="inp !pl-8" autoComplete="off" placeholder="Escreva o nome, a localidade ou o código postal…"
          role="combobox" aria-expanded={aberto} aria-controls={lista} aria-autocomplete="list"
          aria-activedescendant={aberto && itens[ativo] ? `${lista}-${itens[ativo].id}` : undefined}
          value={texto}
          onChange={(e) => { setTexto(e.target.value); setAberto(true); setAtivo(0) }}
          onFocus={() => setAberto(true)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setAberto(true); setAtivo((a) => Math.min(a + 1, itens.length - 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setAtivo((a) => Math.max(a - 1, 0)) }
            else if (e.key === 'Enter' && aberto && itens[ativo]) { e.preventDefault(); escolher(itens[ativo]) }
            else if (e.key === 'Escape') setAberto(false)
          }} />
      </div>
      {aberto && (
        <div id={lista} role="listbox" className="absolute z-30 mt-1 w-full max-h-72 overflow-y-auto bg-white border border-line rounded-lg shadow-lg py-1">
          {termo.length < 2 ? <div className="px-3 py-2 text-[12.5px] text-ink-60">Escreva pelo menos 2 letras para pesquisar.</div>
            : r.isFetching && !r.data ? <div className="px-3 py-2"><Spinner /></div>
            : itens.length === 0 ? <div className="px-3 py-2 text-[12.5px] text-ink-60">Nenhuma loja encontrada.</div>
            : itens.map((l, i) => (
              <div key={l.id} id={`${lista}-${l.id}`} role="option" aria-selected={i === ativo}
                onMouseDown={(e) => { e.preventDefault(); escolher(l) }} onMouseEnter={() => setAtivo(i)}
                className={`px-3 py-1.5 cursor-pointer ${i === ativo ? 'bg-petrol-50' : ''}`}>
                <div className="text-sm flex items-center gap-2">
                  <span className="font-medium">{l.nome}</span>
                  {usadas?.has(l.id) && <span className="text-[11px] text-warn-fg">já está no contrato</span>}
                </div>
                <div className="text-xs text-ink-60">{[l.insignia?.nome, l.zona?.nome, l.localidade, l.codigo_postal].filter(Boolean).join(' · ')}</div>
              </div>
            ))}
          {itens.length === 30 && <div className="px-3 py-1.5 text-[11.5px] text-ink-60 border-t border-line-soft">A mostrar as primeiras 30 — refine a pesquisa.</div>}
        </div>
      )}
    </div>
  )
}
