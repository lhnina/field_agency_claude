import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BotaoEstado, MostrarInativos } from '../components/Estado'
import { AcaoIcone, Badge, Button, Card, ErrorBox, Icon, Loading, useToast } from '../components/ui'
import { InsigniaLogo } from '../components/InsigniaLogo'
import { api, apiForm, session } from '../lib/api'

type Item = { id: number; nome: string; ativo: boolean; logo_v?: number | null }

/** Tabelas auxiliares (zonas e insígnias): criar, renomear, desativar. */
export default function Tabelas() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <Tabela path="zonas" titulo="Zonas" ajuda="Usadas em lojas e colaboradores para o planeamento e os feriados municipais." />
      <Tabela path="insignias" titulo="Insígnias (cadeias)" ajuda="Cadeias de distribuição a que pertencem as lojas." />
    </div>
  )
}

export function Tabela({ path, titulo, ajuda, logos }: { path: string; titulo: string; ajuda: string; logos?: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const pode = ['administrador', 'gestor', 'gestor_conta'].includes(session.user()?.perfil ?? '')
  const [inativos, setInativos] = useState(false)
  const [novo, setNovo] = useState('')
  const [edit, setEdit] = useState<{ id: number; nome: string } | null>(null)
  const q = useQuery({ queryKey: [path, 'gestao', inativos], queryFn: () => api<Item[]>(`/${path}`, { params: { inativos } }) })
  const refresh = () => qc.invalidateQueries({ queryKey: [path] })
  const criar = useMutation({
    mutationFn: () => api(`/${path}`, { method: 'POST', body: { nome: novo.trim() } }),
    onSuccess: () => { setNovo(''); refresh(); toast('Criado') }, onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })
  const renomear = useMutation({
    mutationFn: (v: { id: number; nome: string }) => api(`/${path}/${v.id}`, { method: 'PUT', body: { nome: v.nome.trim() } }),
    onSuccess: () => { setEdit(null); refresh(); toast('Nome atualizado') }, onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })
  const logo = useMutation({
    mutationFn: ({ id, ficheiro }: { id: number; ficheiro: File | null }) => ficheiro
      ? apiForm(`/${path}/${id}/logo`, 'POST', { ficheiro }) : api(`/${path}/${id}/logo`, { method: 'DELETE' }),
    onSuccess: (_, v) => { refresh(); qc.invalidateQueries({ queryKey: ['lojas'] }); toast(v.ficheiro ? 'Logótipo guardado' : 'Logótipo retirado') },
    onError: (e) => toast(e instanceof Error ? e.message : 'Erro', 'err'),
  })
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 px-[18px] py-3 border-b border-line-soft">
        <h3 className="text-[14.5px] font-semibold">{titulo}</h3>
        <span className="flex-1" />
        <MostrarInativos value={inativos} onChange={setInativos} />
      </div>
      <p className="px-[18px] pt-3 text-[12.5px] text-ink-60">{ajuda}</p>
      {pode && (
        <form className="flex gap-2 px-[18px] py-3" onSubmit={(e) => { e.preventDefault(); if (novo.trim()) criar.mutate() }}>
          <input className="inp" placeholder="Nome" aria-label={`Novo registo em ${titulo}`} value={novo} onChange={(e) => setNovo(e.target.value)} />
          <Button type="submit" icon="plus" disabled={!novo.trim()} loading={criar.isPending}>Acrescentar</Button>
        </form>
      )}
      {q.isLoading ? <Loading /> : q.error ? <div className="p-4"><ErrorBox error={q.error} /></div> : (
        <ul className="divide-y divide-line-soft border-t border-line-soft">
          {q.data?.map((i) => (
            <li key={i.id} className={`flex items-center gap-2 px-[18px] py-2 ${i.ativo ? '' : 'opacity-60'}`}>
              {edit?.id === i.id ? (
                <form className="flex gap-2 flex-1" onSubmit={(e) => { e.preventDefault(); renomear.mutate(edit) }}>
                  <input className="inp" autoFocus aria-label="Novo nome" value={edit.nome} onChange={(e) => setEdit({ ...edit, nome: e.target.value })} />
                  <Button type="submit" size="sm" variant="primary" disabled={!edit.nome.trim()}>Guardar</Button>
                  <Button size="sm" variant="ghost" onClick={() => setEdit(null)}>Cancelar</Button>
                </form>
              ) : (
                <>
                  {logos && (pode ? (
                    <label title={i.logo_v ? 'Trocar o logótipo' : 'Carregar logótipo (PNG, JPG, SVG; até 1 MB)'} className="cursor-pointer rounded-md hover:ring-2 hover:ring-petrol-100">
                      {i.logo_v ? <InsigniaLogo id={i.id} v={i.logo_v} nome={i.nome} size={32} />
                        : <span className="grid place-items-center w-8 h-8 rounded-md border border-dashed border-line-strong text-ink-60"><Icon name="plus" size={14} /></span>}
                      <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif" className="sr-only" aria-label={`Logótipo de ${i.nome}`}
                        onChange={(e) => { const fch = e.target.files?.[0]; if (fch) logo.mutate({ id: i.id, ficheiro: fch }); e.target.value = '' }} />
                    </label>
                  ) : <InsigniaLogo id={i.id} v={i.logo_v} nome={i.nome} size={32} inicial />)}
                  <span className="text-[13.5px] font-medium">{i.nome}</span>{!i.ativo && <Badge>Inativo</Badge>}
                  <span className="flex-1" />
                  {logos && pode && i.logo_v ? <AcaoIcone icon="x" label={`Retirar o logótipo de ${i.nome}`} onClick={() => logo.mutate({ id: i.id, ficheiro: null })} /> : null}
                  {pode && <AcaoIcone icon="edit" label={`Renomear ${i.nome}`} onClick={() => setEdit({ id: i.id, nome: i.nome })} />}
                  {pode && <BotaoEstado icone url={`/${path}/${i.id}/estado`} ativo={i.ativo} nome={i.nome} invalidar={[path]} />}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
