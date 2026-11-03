import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, session } from '../lib/api'
import { Badge, Button, ErrorBox, Modal, useToast } from './ui'
import { MesSeletor } from './DataInput'

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
export const nomeMes = (m: string) => { const [y, mm] = m.split('-').map(Number); return `${MESES[mm - 1]} ${y}` }
export const mesAnterior = () => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }
export const mesAtual = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }

export function MesInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="inline-flex items-center gap-2 h-9 pl-3 pr-3 rounded-lg border border-line-strong bg-white text-[13px] text-ink-80">
      Mês
      <MesSeletor value={value} max={mesAtual()} onChange={onChange} />
    </div>
  )
}

/** Estado do período e ações de fecho/reabertura. */
export function FechoPeriodo({ tipo, mes, area, fechado, bloqueio, onDone, descricao }: {
  tipo: 'faturacao' | 'remuneracao'; mes: string; area?: string; fechado: boolean; bloqueio?: string | null; onDone: () => void; descricao: string
}) {
  const toast = useToast()
  const perfil = session.user()?.perfil ?? ''
  const podeFechar = ['administrador', 'direcao', 'financeiro'].includes(perfil)
  const podeReabrir = ['administrador', 'direcao'].includes(perfil)
  const [confirmar, setConfirmar] = useState<'fechar' | 'reabrir' | null>(null)
  const passado = mes < mesAtual()
  const m = useMutation({
    mutationFn: (acao: 'fechar' | 'reabrir') => api(`/periodos/${acao}`, { method: 'POST', body: { tipo, mes, area: area ?? '*' } }),
    onSuccess: (_, acao) => { setConfirmar(null); toast(acao === 'fechar' ? `${nomeMes(mes)} fechado` : `${nomeMes(mes)} reaberto`, acao === 'fechar' ? 'ok' : 'warn'); onDone() },
  })
  return (
    <>
      {fechado ? <Badge tone="ok" dot>Período fechado</Badge> : <Badge tone={passado ? 'warn' : 'neu'} dot>{passado ? 'Período aberto' : 'Mês em curso'}</Badge>}
      {fechado
        ? podeReabrir && <Button onClick={() => setConfirmar('reabrir')}>Reabrir</Button>
        : <Button variant="primary" icon="check" disabled={!podeFechar || !passado || !!bloqueio}
            title={!podeFechar ? 'Só Direção, Financeiro ou Administrador' : !passado ? 'Só meses terminados' : bloqueio ?? undefined}
            onClick={() => setConfirmar('fechar')}>Fechar período</Button>}
      {confirmar && (
        <Modal title={confirmar === 'fechar' ? `Fechar ${nomeMes(mes)}` : `Reabrir ${nomeMes(mes)}`} onClose={() => setConfirmar(null)}
          footer={<><Button variant="ghost" onClick={() => setConfirmar(null)}>Cancelar</Button>
            <Button variant="primary" loading={m.isPending} onClick={() => m.mutate(confirmar)}>{confirmar === 'fechar' ? 'Fechar período' : 'Reabrir período'}</Button></>}>
          <p className="text-[13.5px]">{confirmar === 'fechar'
            ? `${descricao} Depois do fecho, os serviços deste mês deixam de poder ser alterados; as correções passam a ser feitas como ajuste no mês seguinte.`
            : 'A reabertura fica registada na auditoria. Use-a só para corrigir erros antes de exportar.'}</p>
          {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
        </Modal>
      )}
    </>
  )
}
