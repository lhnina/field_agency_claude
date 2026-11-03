import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { AcaoIcone, Button, ErrorBox, Modal, useToast } from './ui'

/** Desativar/reativar um registo. Nada é apagado: fica inativo e mantém o histórico. */
export function BotaoEstado({ url, ativo, nome, invalidar, size = 'sm', icone }: {
  url: string; ativo: boolean; nome: string; invalidar: string[]; size?: 'sm' | 'md'
  /** Nas grelhas: só o ícone (texto ao passar o rato). */
  icone?: boolean
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const [confirmar, setConfirmar] = useState(false)
  const m = useMutation({
    mutationFn: (v: boolean) => api(url, { method: 'POST', body: { ativo: v } }),
    onSuccess: (_, v) => {
      invalidar.forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
      setConfirmar(false)
      toast(v ? `${nome} reativado` : `${nome} desativado`, v ? 'ok' : 'warn')
    },
    onError: (e) => { if (!confirmar) toast(e instanceof Error ? e.message : 'Erro', 'err') },
  })
  if (!ativo) return icone
    ? <AcaoIcone icon="hist" label={`Reativar ${nome}`} loading={m.isPending} onClick={() => m.mutate(true)} />
    : <Button size={size} icon="hist" loading={m.isPending} onClick={() => m.mutate(true)}>Reativar</Button>
  return (
    <>
      {icone
        ? <AcaoIcone icon="trash" tom="perigo" label={`Desativar ${nome}`} onClick={() => { m.reset(); setConfirmar(true) }} />
        : <Button size={size} variant="danger" onClick={() => { m.reset(); setConfirmar(true) }}>Desativar</Button>}
      {confirmar && (
        <Modal title={`Desativar ${nome}`} onClose={() => setConfirmar(false)}
          footer={<><Button variant="ghost" onClick={() => setConfirmar(false)}>Cancelar</Button>
            <Button variant="primary" className="!bg-err !border-err" loading={m.isPending} onClick={() => m.mutate(false)}>Desativar</Button></>}>
          <p className="text-[13.5px]">O registo deixa de aparecer nas listas e nas seleções, mas não é apagado. Todo o histórico se mantém, e pode reativá-lo a qualquer momento com "Mostrar inativos".</p>
          {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
        </Modal>
      )}
    </>
  )
}

export function MostrarInativos({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-[13px] text-ink-80 whitespace-nowrap">
      <input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={value} onChange={(e) => onChange(e.target.checked)} />Mostrar inativos
    </label>
  )
}

export function Facto({ k, v, href }: { k: string; v?: string | null; href?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-60">{k}</dt>
      <dd className="text-[13.5px] font-medium truncate" title={v ?? undefined}>
        {v ? (href ? <a href={href} target={href.startsWith('http') ? '_blank' : undefined} rel="noreferrer" className="text-petrol-600 hover:underline">{v}</a> : v) : '—'}
      </dd>
    </div>
  )
}
