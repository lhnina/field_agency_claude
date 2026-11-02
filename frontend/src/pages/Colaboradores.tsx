import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, useToast } from '../components/ui'
import { api } from '../lib/api'
import { VINCULO, dataCurta, eur } from '../lib/format'
import type { Colaborador, IdNome, Vinculo } from '../lib/types'

const DL = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D']
const SEGMENTOS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' }, { value: 'muito_curta_duracao', label: 'Muito curta duração' }, { value: 'recibos_verdes', label: 'Recibos verdes' },
  { value: 'a_termo', label: 'A termo' }, { value: 'sem_termo', label: 'Sem termo' },
]

export default function Colaboradores() {
  const [vinculo, setVinculo] = useState('')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const [edit, setEdit] = useState<Colaborador | 'novo' | null>(null)
  const lista = useQuery({ queryKey: ['colaboradores', vinculo, q], queryFn: () => api<Colaborador[]>('/colaboradores', { params: { vinculo, q } }) })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const itens = lista.data ?? []
  const atual = itens.find((c) => c.id === sel) ?? itens[0]
  const nomeSup = (id: number | null) => sups.data?.find((s) => s.id === id)?.nome ?? '—'

  return (
    <>
      <PageHeader crumb="Pessoas" title="Colaboradores" sub={`${itens.length} colaboradores ativos${vinculo ? ' neste segmento' : ''}`}>
        <Button variant="primary" icon="plus" onClick={() => setEdit('novo')}>Novo colaborador</Button>
      </PageHeader>
      <div className="flex flex-wrap items-start gap-4">
        <Card className="flex-[999_1_560px] overflow-hidden">
          <div role="tablist" aria-label="Segmentos" className="flex gap-0.5 border-b border-line px-[18px]">
            {SEGMENTOS.map((s) => (
              <button key={s.value} type="button" role="tab" aria-selected={vinculo === s.value} onClick={() => setVinculo(s.value)}
                className={`h-10 px-3 text-[13.5px] -mb-px border-b-2 ${vinculo === s.value ? 'border-petrol-600 text-ink font-medium' : 'border-transparent text-ink-60 hover:text-ink'}`}>{s.label}</button>
            ))}
          </div>
          <div className="px-3.5 py-3">
            <label className="flex items-center gap-2 h-[34px] w-[280px] px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
              <Icon name="search" size={16} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou n.º" aria-label="Pesquisar colaboradores" className="flex-1 min-w-0 bg-transparent outline-none text-[13.5px] text-ink" />
            </label>
          </div>
          {lista.isLoading ? <Loading /> : lista.error ? <div className="p-4"><ErrorBox error={lista.error} /></div> : itens.length === 0 ? <Empty title="Sem colaboradores" /> : (
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>Colaborador</th><th>Vínculo</th><th>Disponibilidade</th><th>Supervisor</th><th className="text-right">Custo/hora</th></tr></thead>
                <tbody>
                  {itens.map((c, i) => (
                    <tr key={c.id} className={atual?.id === c.id ? '[&>td]:!bg-[#EAF4F2]' : ''}>
                      <td>
                        <div className="flex items-center gap-2.5">
                          <Avatar nome={c.nome} tone={i} />
                          <div><button type="button" onClick={() => setSel(c.id)} className="font-medium text-[13.5px] hover:text-petrol-600 hover:underline text-left">{c.nome}</button>
                            <div className="text-xs text-ink-60">N.º {c.numero}{c.funcao ? ` · ${c.funcao}` : ''}{c.zona ? ` · ${c.zona.nome}` : ''}</div></div>
                        </div>
                      </td>
                      <td><Badge tone={VINCULO[c.vinculo].tone}>{VINCULO[c.vinculo].label}</Badge></td>
                      <td><Disp d={c.disponibilidade} /></td>
                      <td className="text-[12.5px] text-ink-60">{nomeSup(c.supervisor_id)}</td>
                      <td className="text-right num">{eur(c.custo_hora)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {atual && (
          <Card className="flex-[0_1_400px] min-w-[320px]">
            <div className="flex gap-3.5 items-start p-[18px]">
              <Avatar nome={atual.nome} size={52} />
              <div className="flex-1 min-w-0">
                <div className="text-[17px] font-semibold tracking-[-0.01em]">{atual.nome}</div>
                <div className="text-[12.5px] text-ink-60">N.º {atual.numero}{atual.funcao ? ` · ${atual.funcao}` : ''}</div>
                <div className="flex gap-1.5 mt-2"><Badge tone="ok" dot>Ativo</Badge><Badge tone={VINCULO[atual.vinculo].tone}>{VINCULO[atual.vinculo].label}</Badge></div>
              </div>
              <Button size="sm" variant="primary" icon="edit" onClick={() => setEdit(atual)}>Editar</Button>
            </div>
            {atual.vinculo === 'recibos_verdes' && <Aviso>Prestador independente: os serviços são propostos e aceites por ele, sem escala imposta.</Aviso>}
            {atual.vinculo === 'muito_curta_duracao' && <Aviso>Contrato de muito curta duração: máximo 35 dias seguidos e 70 dias por ano com a agência. O contador chega no próximo incremento.</Aviso>}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-[18px] py-3.5 border-t border-line-soft">
              {[['Supervisor', nomeSup(atual.supervisor_id)], ['Zona', atual.zona?.nome ?? '—'], ['Início', dataCurta(atual.data_inicio)], ['Custo/hora', eur(atual.custo_hora)],
                ['Telemóvel', atual.telefone ?? '—'], ['Email', atual.email ?? '—']].map(([k, v]) => (
                <div key={k} className="min-w-0"><dt className="text-xs text-ink-60">{k}</dt><dd className="text-[13.5px] font-medium truncate">{v}</dd></div>
              ))}
            </dl>
            <div className="px-[18px] py-3.5 border-t border-line-soft">
              <div className="text-[13px] font-semibold mb-2">Disponibilidade semanal</div>
              <Disp d={atual.disponibilidade} big />
            </div>
          </Card>
        )}
      </div>
      {edit && <ColabDialog c={edit === 'novo' ? null : edit} onClose={() => setEdit(null)} />}
    </>
  )
}

function Aviso({ children }: { children: React.ReactNode }) {
  return <div className="mx-[18px] mb-3.5 rounded-[9px] bg-warn-bg text-[#6B4000] px-3 py-2.5 text-[12.5px] flex gap-2"><Icon name="alert" size={16} />{children}</div>
}

function Disp({ d, big }: { d: string; big?: boolean }) {
  return (
    <div className="flex gap-[3px]" aria-label={`Disponível: ${DL.map((_x, i) => (d[i] === '1' ? ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'][i] : null)).filter(Boolean).join(', ')}`}>
      {DL.map((x, i) => (
        <span key={i} className={`grid place-items-center rounded font-medium ${big ? 'w-8 h-8 text-xs' : 'w-[17px] h-[17px] text-[10.5px]'} ${d[i] === '1' ? 'bg-petrol-100 text-[#0B4D47]' : 'bg-[#EDEFEC] text-ink-60'}`}>{x}</span>
      ))}
    </div>
  )
}

function ColabDialog({ c, onClose }: { c: Colaborador | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const zonas = useQuery({ queryKey: ['zonas'], queryFn: () => api<IdNome[]>('/zonas') })
  const sups = useQuery({ queryKey: ['supervisores'], queryFn: () => api<IdNome[]>('/utilizadores/supervisores') })
  const [f, setF] = useState({
    numero: c?.numero ?? '', nome: c?.nome ?? '', funcao: c?.funcao ?? '', email: c?.email ?? '', telefone: c?.telefone ?? '',
    vinculo: (c?.vinculo ?? 'a_termo') as Vinculo, data_inicio: c?.data_inicio ?? '', zona_id: c?.zona_id ? String(c.zona_id) : '',
    supervisor_id: c?.supervisor_id ? String(c.supervisor_id) : '', custo_hora: c?.custo_hora ?? '', disponibilidade: c?.disponibilidade ?? '1111100',
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })
  const m = useMutation({
    mutationFn: () => api<Colaborador>(c ? `/colaboradores/${c.id}` : '/colaboradores', {
      method: c ? 'PUT' : 'POST',
      body: { ...f, funcao: f.funcao || null, email: f.email || null, telefone: f.telefone || null, data_inicio: f.data_inicio || null,
        zona_id: f.zona_id ? Number(f.zona_id) : null, supervisor_id: f.supervisor_id ? Number(f.supervisor_id) : null,
        custo_hora: Number(String(f.custo_hora).replace(',', '.')) || 0, ativo: true },
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['colaboradores'] }); toast(c ? 'Ficha atualizada' : 'Colaborador criado'); onClose() },
  })
  return (
    <Modal title={c ? `Editar ${c.nome}` : 'Novo colaborador'} onClose={onClose} width={620}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="primary" loading={m.isPending} disabled={!f.nome || !f.numero} onClick={() => m.mutate()}>Guardar</Button></>}>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Nome">{(id) => <input id={id} className="inp" value={f.nome} onChange={set('nome')} />}</Field>
        <Field label="N.º">{(id) => <input id={id} className="inp" value={f.numero} onChange={set('numero')} />}</Field>
        <Field label="Função">{(id) => <input id={id} className="inp" value={f.funcao} onChange={set('funcao')} placeholder="Repositor(a), Promotor(a)…" />}</Field>
        <Field label="Vínculo">{(id) => (
          <select id={id} className="inp" value={f.vinculo} onChange={set('vinculo')}>
            {Object.entries(VINCULO).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>)}</Field>
        <Field label="Zona">{(id) => <select id={id} className="inp" value={f.zona_id} onChange={set('zona_id')}><option value="">—</option>{zonas.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}</select>}</Field>
        <Field label="Supervisor">{(id) => <select id={id} className="inp" value={f.supervisor_id} onChange={set('supervisor_id')}><option value="">—</option>{sups.data?.map((z) => <option key={z.id} value={z.id}>{z.nome}</option>)}</select>}</Field>
        <Field label="Custo por hora (€)" hint="Pode ser definido um custo especial por serviço no contrato">{(id) => <input id={id} inputMode="decimal" className="inp num" value={f.custo_hora} onChange={set('custo_hora')} />}</Field>
        <Field label="Data de início">{(id) => <input id={id} type="date" className="inp" value={f.data_inicio} onChange={set('data_inicio')} />}</Field>
        <Field label="Telemóvel">{(id) => <input id={id} className="inp" value={f.telefone} onChange={set('telefone')} />}</Field>
        <Field label="Email">{(id) => <input id={id} type="email" className="inp" value={f.email} onChange={set('email')} />}</Field>
        <div className="col-span-2">
          <div className="lbl mb-1.5">Disponibilidade semanal</div>
          <div className="flex gap-1.5">
            {['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((d, i) => {
              const on = f.disponibilidade[i] === '1'
              return <button key={d} type="button" aria-pressed={on} onClick={() => setF({ ...f, disponibilidade: f.disponibilidade.slice(0, i) + (on ? '0' : '1') + f.disponibilidade.slice(i + 1) })}
                className={`h-9 w-12 rounded-md text-[13px] font-medium border ${on ? 'bg-petrol-100 border-petrol-600 text-[#0B4D47]' : 'bg-white border-line-strong text-ink-60'}`}>{d}</button>
            })}
          </div>
        </div>
      </div>
      {m.error ? <div className="mt-3"><ErrorBox error={m.error} /></div> : null}
    </Modal>
  )
}
