/** Miniatura do logótipo da insígnia (cadeia). Sem logótipo, não ocupa espaço (ou mostra a inicial, se `inicial`). */
export function InsigniaLogo({ id, v, nome, size = 22, inicial }: { id?: number | null; v?: number | null; nome?: string | null; size?: number; inicial?: boolean }) {
  if (id && v) {
    return (
      <img src={`/api/insignias/${id}/logo?v=${v}`} alt={nome ?? ''} title={nome ?? undefined} loading="lazy"
        style={{ width: size, height: size }} className="flex-none rounded-[5px] object-contain bg-white border border-line-soft p-[1px]" />
    )
  }
  if (!inicial || !nome) return null
  return (
    <span title={nome} style={{ width: size, height: size, fontSize: size * 0.45 }}
      className="flex-none grid place-items-center rounded-[5px] bg-[#EDEFEC] text-ink-60 font-semibold">{nome.slice(0, 1).toUpperCase()}</span>
  )
}
