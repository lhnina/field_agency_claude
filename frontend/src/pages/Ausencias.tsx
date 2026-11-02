import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { api } from '../lib/api'
import { dataCurta, iso } from '../lib/format'
import type { Ausencia, Colaborador } from '../lib/types'

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
  const colabs = useQuery({ queryKey: ['colaboradores'], queryFn: () => api<Colaborador[]>('/colaboradores') })
  const [f, setF] = useState({ colaborador_id: '', tipo: 'ferias', inicio: iso(new Date()), fim: iso(new Date()), observacoes: '' })
  const m = useMutation({
    mutationFn: () => api<Ausencia>('/ausencias', { method: 'POST', body: { ...f, colaborador_id: Number(f.colaborador_id), observacoes: f.observacoes || null } }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: ['ausencias'] }); qc.invalidateQueries({ queryKey: ['planeamento'] })
      toast(a.por_substituir ? `Ausência registada: ${a.por_substituir} serviços por substituir` : 'Ausência registada', a.por_substituir ? 'warn' : 'ok')
      onClose()
    },
  })
  const err = f.fim < f.inicio ? 'A data de fim é anterior à data de início' : null
  return (
    <Modal title="Registar ausência" onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.colaborador_id || !!err} onClick={() => m.mutate()}>Registar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Colaborador" className="col-span-2">{(id) => <select id={id} className="inp" value={f.colaborador_id} onChange={(e) => setF({ ...f, colaborador_id: e.target.value })}><option value="">Escolher…</option>{colabs.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select>}</Field>
        <Field label="Tipo">{(id) => <select id={id} className="inp" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>{Object.entries(TIPO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}</Field>
        <span />
        <Field label="De">{(id) => <input id={id} type="date" className="inp" value={f.inicio} onChange={(e) => setF({ ...f, inicio: e.target.value })} />}</Field>
        <Field label="Até" error={err}>{(id) => <input id={id} type="date" className={`inp ${err ? 'inp-err' : ''}`} value={f.fim} onChange={(e) => setF({ ...f, fim: e.target.value })} />}</Field>
        <Field label="Observações" className="col-span-2">{(id) => <input id={id} className="inp" value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />}</Field>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
