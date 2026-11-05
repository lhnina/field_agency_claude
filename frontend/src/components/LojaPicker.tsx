import { api } from '../lib/api'
import type { Loja } from '../lib/types'
import { Pesquisa } from './Pesquisa'
import { InsigniaLogo } from './InsigniaLogo'

type Props = { id?: string; value: { id: number; nome: string } | null; onChange: (loja: Loja | null) => void; usadas?: Set<number> }

/** Escolha de loja por pesquisa (nome, localidade, código postal ou morada), adequada a milhares de lojas. */
export function LojaPicker({ id, value, onChange, usadas }: Props) {
  return (
    <Pesquisa<Loja> id={id} chave="lojas" icon="store" value={value} onChange={onChange}
      placeholder="Escreva o nome, o código ERP, a localidade ou o código postal…"
      pesquisar={(q, limite) => api<Loja[]>('/lojas', { params: { q, limite } })}
      render={(l) => <>
        <div className="text-sm flex items-center gap-2">
          <InsigniaLogo id={l.insignia?.id} v={l.insignia?.logo_v} nome={l.insignia?.nome} size={18} />
          <span className="font-medium">{l.nome}</span>
          {usadas?.has(l.id) && <span className="text-[11px] text-warn-fg">já está no contrato</span>}
        </div>
        <div className="text-xs text-ink-60">{[l.codigo_erp && `ERP ${l.codigo_erp}`, l.insignia?.nome, l.zona?.nome, l.localidade, l.codigo_postal].filter(Boolean).join(' · ')}</div>
      </>} />
  )
}
