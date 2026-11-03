import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, ErrorBox, Field, IconButton, Loading, Modal, useToast } from '../components/ui'
import { api, session } from '../lib/api'
import { dataCurta, diaSemana } from '../lib/format'
import type { IdNome } from '../lib/types'

type F = { id: number | null; data: string; nome: string; ambito: 'nacional' | 'agencia' | 'zona'; zona_id: number | null; zona: string | null }

export default function Feriados() {
  const qc = useQueryClient()
  const toast = useToast()
  const [ano, setAno] = useState(new Date().getFullYear())
  const [novo, setNovo] = useState(false)
  const pode = ['administrador', 'direcao', 'gestor'].includes(session.user()?.perfil ?? '')
  const q = useQuery({ queryKey: ['feriados', ano], queryFn: () => api<F[]>('/feriados', { params: { ano } }) })
  const apagar = useMutation({
    mutationFn: (id: number) => api(`/feriados/${id}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['feriados'] }); toast('Feriado removido. Os serviços já reagendados mantêm-se no novo dia.', 'warn') },
  })
  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 px-[18px] py-3 border-b border-line-soft">
          <h3 className="text-[14.5px] font-semibold">Feriados</h3>
          <div className="flex items-center gap-1 ml-2">
            <IconButton icon="cl" label="Ano anterior" onClick={() => setAno(ano - 1)} className="!w-8 !h-8" />
            <span className="font-semibold num w-12 text-center">{ano}</span>
            <IconButton icon="cr" label="Ano seguinte" onClick={() => setAno(ano + 1)} className="!w-8 !h-8" />
          </div>
          <span className="flex-1" />
          {pode && <Button size="sm" variant="primary" icon="plus" onClick={() => setNovo(true)}>Feriado municipal ou da agência</Button>}
        </div>
        {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : (
          <table className="tbl">
            <thead><tr><th>Data</th><th>Feriado</th><th>Âmbito</th><th /></tr></thead>
            <tbody>{q.data?.map((f, i) => (
              <tr key={`${f.data}-${i}`}>
                <td className="num whitespace-nowrap">{diaSemana(f.data)}, {dataCurta(f.data)}</td>
                <td className="font-medium">{f.nome}</td>
                <td>{f.ambito === 'nacional' ? <Badge>Nacional</Badge> : f.ambito === 'zona' ? <Badge tone="info">Zona {f.zona}</Badge> : <Badge tone="warn">Toda a agência</Badge>}</td>
                <td className="text-right">{f.id && pode && <Button size="sm" variant="danger" onClick={() => apagar.mutate(f.id!)}>Remover</Button>}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Card>
      <p className="text-[12.5px] text-ink-60">Os feriados nacionais são calculados automaticamente para qualquer ano. Num feriado, o serviço passa para outro dia útil, de preferência na mesma semana.</p>
      {novo && <NovoFeriado onClose={() => setNovo(false)} />}
    </>
  )
}

function NovoFeriado({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const [f, setF] = useState({ data: '', nome: '', zona_id: '' })
  const m = useMutation({
    mutationFn: () => api<{ servicos_reagendados: number }>('/feriados', { method: 'POST', body: { data: f.data, nome: f.nome, zona_id: f.zona_id ? Number(f.zona_id) : null } }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['feriados'] }); qc.invalidateQueries({ queryKey: ['planeamento'] })
      toast(r.servicos_reagendados ? `Feriado criado: ${r.servicos_reagendados} serviços passaram para outro dia` : 'Feriado criado'); onClose()
    },
  })
  return (
    <Modal title="Novo feriado" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.data || !f.nome} onClick={() => m.mutate()}>Criar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Data">{(id) => <input id={id} type="date" className="inp" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} />}</Field>
        <Field label="Aplica-se a" hint="Municipal: só as lojas da zona">{(id) => (
          <select id={id} className="inp" value={f.zona_id} onChange={(e) => setF({ ...f, zona_id: e.target.value })}>
            <option value="">Toda a agência</option>{zonas.data?.map((z) => <option key={z.id} value={z.id}>Zona {z.nome}</option>)}
          </select>)}</Field>
        <Field label="Nome" className="col-span-2">{(id) => <input id={id} className="inp" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} placeholder="Ex.: Feriado municipal de Lisboa (Santo António)" />}</Field>
      </div>
      <p className="text-xs text-ink-60 mt-3">Os serviços já planeados nessa data, ainda não executados, passam automaticamente para outro dia.</p>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
