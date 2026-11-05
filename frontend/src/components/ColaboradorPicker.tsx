import { api } from '../lib/api'
import { horas, vinculoTexto } from '../lib/format'
import type { Colaborador } from '../lib/types'
import { Pesquisa } from './Pesquisa'

type Props = { id?: string; value: { id: number; nome: string } | null; onChange: (c: Colaborador | null) => void; zonaPreferida?: string | null }

/** Escolha de colaborador por pesquisa (nome, n.º ou função). Os da zona da loja aparecem primeiro. */
export function ColaboradorPicker({ id, value, onChange, zonaPreferida }: Props) {
  const daZona = (c: Colaborador) => (zonaPreferida && c.zona?.nome === zonaPreferida ? 0 : 1)
  return (
    <Pesquisa<Colaborador> id={id} chave="colaboradores" icon="user" value={value} onChange={onChange}
      placeholder="Escreva o nome ou o n.º do colaborador…"
      pesquisar={(q, limite) => api<Colaborador[]>('/colaboradores', { params: { q, limite } })}
      ordenar={(a, b) => daZona(a) - daZona(b)}
      render={(c) => <>
        <div className="text-sm flex items-center gap-2">
          <span className="font-medium">{c.nome}</span>
          {zonaPreferida && c.zona?.nome === zonaPreferida && <span className="text-[11px] text-ok-fg">zona da loja</span>}
          <span className="ml-auto text-xs text-ink-60 num">{c.vinculo === 'recibos_verdes' ? 'prestador' : `${horas(c.horas_afetadas)} afetas/sem`}</span>
        </div>
        <div className="text-xs text-ink-60">{[`N.º ${c.numero}`, c.funcao, c.zona?.nome, vinculoTexto(c)].filter(Boolean).join(' · ')}</div>
      </>} />
  )
}
