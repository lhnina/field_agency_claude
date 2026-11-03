import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AcaoIcone, Badge, Button, Card, ErrorBox, Icon, PageHeader, Spinner, useToast } from '../components/ui'
import { ApiError, api, session } from '../lib/api'

type Tipo = 'clientes' | 'lojas' | 'colaboradores' | 'contratos'
type Linha = { linha: number; chave: string; acao: string; erros: string[]; avisos: string[] }
type Res = { linhas: Linha[]; resumo: { total: number; com_erros: number; criar?: number; atualizar?: number }; importado?: boolean }

const PASSOS: { tipo: Tipo; titulo: string; texto: string }[] = [
  { tipo: 'clientes', titulo: '1 · Clientes e marcas', texto: 'Nome, NIF, código ERP, morada, contactos, gestor de conta e marcas.' },
  { tipo: 'lojas', titulo: '2 · Lojas', texto: 'Insígnia, zona, morada, horários, contacto e supervisor.' },
  { tipo: 'colaboradores', titulo: '3 · Colaboradores', texto: 'N.º, vínculo, zona, supervisor, custo/hora e disponibilidade.' },
  { tipo: 'contratos', titulo: '4 · Contratos', texto: 'Uma linha por loja, com as horas por dia, o preço e o colaborador afeto.' },
]

async function enviar(tipo: Tipo, f: File, confirmar: boolean): Promise<Res> {
  const fd = new FormData()
  fd.append('ficheiro', f)
  const r = await fetch(`/api/importacao/${tipo}?confirmar=${confirmar}`, { method: 'POST', headers: { Authorization: `Bearer ${session.token()}` }, body: fd })
  const body = await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(r.status, typeof body?.detail === 'string' ? body.detail : `Erro ${r.status}`)
  return body
}

export default function Importacao() {
  const qc = useQueryClient()
  const toast = useToast()
  const [tipo, setTipo] = useState<Tipo>('clientes')
  const [ficheiro, setFicheiro] = useState<File | null>(null)
  const [res, setRes] = useState<Res | null>(null)
  const [erro, setErro] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [soErros, setSoErros] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const cont = useQuery({ queryKey: ['importacao-contagens'], queryFn: () => api<Record<Tipo, number>>('/importacao/contagens') })

  const escolher = (t: Tipo) => { setTipo(t); setFicheiro(null); setRes(null); setErro(null); if (input.current) input.current.value = '' }

  async function modelo() {
    const r = await fetch(`/api/importacao/modelo/${tipo}`, { headers: { Authorization: `Bearer ${session.token()}` } })
    if (!r.ok) { toast('Sem permissão para este modelo', 'err'); return }
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement('a'); a.href = url; a.download = `modelo-${tipo}.xlsx`; a.click(); URL.revokeObjectURL(url)
  }

  async function correr(f: File, confirmar: boolean) {
    setBusy(true); setErro(null)
    try {
      const r = await enviar(tipo, f, confirmar)
      setRes(r)
      if (confirmar) {
        toast(`Importação concluída: ${r.resumo.criar ?? 0} criados, ${r.resumo.atualizar ?? 0} atualizados`)
        qc.invalidateQueries()
        setFicheiro(null); setRes(null); if (input.current) input.current.value = ''
      }
    } catch (e) { setErro(e); setRes(null) } finally { setBusy(false) }
  }

  const linhas = (res?.linhas ?? []).filter((l) => !soErros || l.erros.length)

  return (
    <>
      <PageHeader crumb="Configuração" title="Importação de dados"
        sub="Carga inicial a partir de Excel. Importe pela ordem indicada: os contratos usam os clientes, as lojas e os colaboradores já importados." />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {PASSOS.map((p) => (
          <button key={p.tipo} type="button" onClick={() => escolher(p.tipo)} aria-pressed={tipo === p.tipo}
            className={`card text-left px-[18px] py-4 transition-colors ${tipo === p.tipo ? '!border-petrol-600 ring-2 ring-petrol-600/15' : 'hover:border-line-strong'}`}>
            <div className="font-semibold text-[14.5px]">{p.titulo}</div>
            <div className="text-[12.5px] text-ink-60 mt-1">{p.texto}</div>
            <div className="text-xs text-ink-60 mt-2.5 num">{cont.data ? `${cont.data[p.tipo]} registos na plataforma` : ' '}</div>
          </button>
        ))}
      </div>

      <Card className="p-[18px] flex flex-wrap items-center gap-3">
        <AcaoIcone icon="download" label="Descarregar modelo Excel" onClick={modelo} className="!w-9 !h-9 border border-line-strong bg-white" />
        <label className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border border-dashed border-line-strong bg-[#FAFBF9] text-[13.5px] cursor-pointer hover:border-petrol-600">
          <Icon name="plus" size={16} />{ficheiro ? ficheiro.name : 'Escolher ficheiro .xlsx'}
          <input ref={input} type="file" accept=".xlsx" className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0] ?? null; setFicheiro(f); setRes(null); if (f) correr(f, false) }} />
        </label>
        {busy && <span className="flex items-center gap-2 text-[13px] text-ink-60"><Spinner />A processar…</span>}
        <span className="flex-1" />
        {res && <>
          <Badge>{res.resumo.total} linhas</Badge>
          {!!res.resumo.criar && <Badge tone="ok">{res.resumo.criar} a criar</Badge>}
          {!!res.resumo.atualizar && <Badge tone="info">{res.resumo.atualizar} a atualizar</Badge>}
          <Badge tone={res.resumo.com_erros ? 'err' : 'ok'} dot>{res.resumo.com_erros} com erros</Badge>
          <Button variant="primary" icon="check" disabled={!ficheiro || res.resumo.com_erros > 0 || busy} onClick={() => ficheiro && correr(ficheiro, true)}
            title={res.resumo.com_erros ? 'Corrija as linhas com erros no Excel e volte a carregar' : undefined}>Importar</Button>
        </>}
      </Card>
      {erro ? <ErrorBox error={erro} /> : null}

      {res && (
        <Card className="overflow-hidden">
          <div className="flex items-center gap-3 px-3.5 py-3 border-b border-line-soft">
            <h3 className="text-[14.5px] font-semibold">Pré-visualização</h3>
            <span className="text-[12.5px] text-ink-60">Ainda não foi gravado nada.</span>
            <span className="flex-1" />
            <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" className="w-4 h-4 accent-petrol-600" checked={soErros} onChange={(e) => setSoErros(e.target.checked)} />Só linhas com erros</label>
          </div>
          <div className="overflow-x-auto max-h-[560px]">
            <table className="tbl">
              <thead><tr><th className="w-16">Linha</th><th>Registo</th><th>Ação</th><th>Erros e avisos</th></tr></thead>
              <tbody>{linhas.map((l) => (
                <tr key={l.linha} className={l.erros.length ? '[&>td]:!bg-err-bg/40' : ''}>
                  <td className="num text-ink-60">{l.linha}</td>
                  <td className="font-medium">{l.chave || '—'}</td>
                  <td>{l.erros.length ? <Badge tone="err">Erro</Badge> : l.acao === 'atualizar' ? <Badge tone="info">Atualizar</Badge> : <Badge tone="ok">Criar</Badge>}</td>
                  <td className="text-[12.5px]">
                    {l.erros.map((e) => <div key={e} className="text-err-fg">{e}</div>)}
                    {l.avisos.map((a) => <div key={a} className="text-warn-fg">{a}</div>)}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  )
}
