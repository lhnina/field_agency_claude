import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { DataInput } from '../components/DataInput'
import { ColaboradorPicker } from '../components/ColaboradorPicker'
import { api } from '../lib/api'
import { dataCurta, iso } from '../lib/format'
import type { Ausencia } from '../lib/types'

const TIPO: Record<string, string> = { ferias: 'Férias', falta: 'Falta', baixa: 'Baixa', indisponivel: 'Indisponibilidade' }

export default function Ausencias() {
  const nav = useNavigate()
  const [novo, setNovo] = useState(false)
  const hoje = iso(new Date())
  const q = useQuery({ queryKey: ['ausencias'], queryFn: () => api<Ausencia[]>('/ausencias', { params: { desde: hoje } }) })
  return (
    <>
      <PageHeader crumb="Operação" title="Ausências e substituições" sub="Ausências em curso e futuras. Os serviços afetados aparecem no planeamento para substituir.">
        <Button variant="primary" icon="plus" onClick={() => setNovo(true)}>Registar ausência</Button>
      </PageHeader>
      <Card className="overflow-hidden">
        {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : !q.data?.length ? <Empty title="Sem ausências registadas" /> : (
          <table className="tbl">
            <thead><tr><th>Colaborador</th><th>Tipo</th><th>Período</th><th className="text-right">Serviços afetados</th><th>Situação</th><th /></tr></thead>
            <tbody>{q.data.map((a, i) => (
              <tr key={a.id}>
                <td><div className="flex items-center gap-2.5"><Avatar nome={a.colaborador_nome} tone={i} /><span className="font-medium">{a.colaborador_nome}</span></div></td>
                <td>{TIPO[a.tipo] ?? a.tipo}</td>
                <td className="num">{dataCurta(a.inicio)} – {dataCurta(a.fim)}</td>
                <td className="text-right num">{a.ocorrencias_afetadas}</td>
                <td>{a.por_substituir ? <Badge tone="err" dot>{a.por_substituir} por substituir</Badge> : <Badge tone="ok" dot>Tudo substituído</Badge>}</td>
                <td className="text-right"><Button size="sm" onClick={() => nav('/planeamento')}>Abrir planeamento</Button></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Card>
      {novo && <NovaAusencia onClose={() => setNovo(false)} />}
    </>
  )
}

function NovaAusencia({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [colab, setColab] = useState<{ id: number; nome: string } | null>(null)
  const [f, setF] = useState({ tipo: 'ferias', inicio: iso(new Date()), fim: iso(new Date()), observacoes: '' })
  const m = useMutation({
    mutationFn: () => api<Ausencia>('/ausencias', { method: 'POST', body: { ...f, colaborador_id: colab!.id, observacoes: f.observacoes || null } }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: ['ausencias'] }); qc.invalidateQueries({ queryKey: ['planeamento'] })
      toast(a.por_substituir ? `Ausência registada: ${a.por_substituir} serviços por substituir` : 'Ausência registada', a.por_substituir ? 'warn' : 'ok')
      onClose()
    },
  })
  const err = f.fim < f.inicio ? 'A data de fim é anterior à data de início' : null
  return (
    <Modal title="Registar ausência" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!colab || !!err} onClick={() => m.mutate()}>Registar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Colaborador" className="col-span-2">{(id) => <ColaboradorPicker id={id} value={colab} onChange={(c) => setColab(c ? { id: c.id, nome: c.nome } : null)} />}</Field>
        <Field label="Tipo">{(id) => <select id={id} className="inp" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>{Object.entries(TIPO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Field>
        <span />
        <Field label="De">{(id) => <DataInput id={id} value={f.inicio} onChange={(v) => setF({ ...f, inicio: v })} />}</Field>
        <Field label="Até" error={err}>{(id) => <DataInput id={id} invalid={!!err} value={f.fim} min={f.inicio || undefined} onChange={(v) => setF({ ...f, fim: v })} />}</Field>
        <Field label="Observações" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
