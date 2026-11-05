import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { MinhaSenhaDialog } from '../pages/Utilizadores'
import simbolo from '../assets/argos-simbolo.png'
import wordmark from '../assets/argos-wordmark.png'
import { session } from '../lib/api'
import { Avatar, Icon } from './ui'
import type { IconName } from './ui'

type Item = { to?: string; icon: IconName; label: string }
const GRUPOS: { titulo?: string; itens: Item[] }[] = [
  { itens: [{ to: '/', icon: 'dash', label: 'Dashboard' }] },
  { titulo: 'Operação', itens: [
    { to: '/planeamento', icon: 'cal', label: 'Planeamento' },
    { to: '/validacao', icon: 'check-sq', label: 'Validação de horas' },
    { to: '/ausencias', icon: 'user-x', label: 'Ausências' },
    { to: '/logistica', icon: 'truck', label: 'Logística' },
  ] },
  { titulo: 'Comercial', itens: [
    { to: '/contratos', icon: 'file', label: 'Contratos' },
    { to: '/clientes', icon: 'store', label: 'Clientes e lojas' },
  ] },
  { titulo: 'Pessoas', itens: [
    { to: '/colaboradores', icon: 'users', label: 'Colaboradores' },
    { to: '/documentacao', icon: 'shield', label: 'Documentação' },
  ] },
  { titulo: 'Financeiro', itens: [
    { icon: 'trend', label: 'Rentabilidade' },
    { to: '/prefaturacao', icon: 'receipt', label: 'Pré-faturação' },
    { to: '/apuramentos', icon: 'calc', label: 'Apuramentos' },
  ] },
]

const PERFIL: Record<string, string> = {
  administrador: 'Administrador', direcao: 'Direção', gestor: 'Gestor operacional', gestor_conta: 'Gestor de conta', supervisor: 'Supervisor',
  rh: 'Recursos humanos', financeiro: 'Financeiro', colaborador: 'Colaborador',
}

export default function Layout() {
  const user = session.user()
  const nav = useNavigate()
  const [senha, setSenha] = useState(false)
  return (
    <div className="flex flex-wrap min-h-screen">
      <nav aria-label="Menu principal" className="flex-[1_0_248px] max-w-sidebar bg-petrol-900 text-[#C9D6D3] flex flex-col px-3 pt-[18px] pb-3.5">
        <div className="flex items-center gap-3 px-2 pb-3.5">
          <img src={simbolo} alt="" className="w-11 h-11 flex-none" />
          <div className="leading-tight"><img src={wordmark} alt="Argos" className="h-[15px] w-auto mb-1" /><div className="text-xs text-[#93AAA6]">Gestão operacional</div></div>
        </div>
        {GRUPOS.map((g, i) => (
          <div key={i} className="mt-3">
            {g.titulo && <h6 className="px-2.5 mb-1 text-2xs font-medium tracking-[.07em] uppercase text-[#86A09B]">{g.titulo}</h6>}
            {g.itens.map((it) => it.to ? (
              <NavLink key={it.label} to={it.to} end={it.to === '/'}
                className={({ isActive }) => `flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] ${isActive ? 'bg-[#1F4744] text-white font-medium [&_svg]:text-amber-400' : 'hover:bg-petrol-800 hover:text-white'}`}>
                <Icon name={it.icon} /><span>{it.label}</span>
              </NavLink>
            ) : (
              <span key={it.label} aria-disabled="true" title="Disponível num próximo incremento"
                className="flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] text-[#86A09B] cursor-default">
                <Icon name={it.icon} /><span className="truncate">{it.label}</span>
                <span className="ml-auto flex-none text-2xs px-1.5 rounded-full bg-[#1F4442] text-[#A9BDB9]">em breve</span>
              </span>
            ))}
          </div>
        ))}
        <div className="mt-auto pt-3.5 border-t border-[#1F4442]">
          <NavLink to="/importacao" className={({ isActive }) => `flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] ${isActive ? 'bg-[#1F4744] text-white font-medium [&_svg]:text-amber-400' : 'hover:bg-petrol-800 hover:text-white'}`}>
            <Icon name="file" /><span>Importar dados</span>
          </NavLink>
          <NavLink to="/configuracao" className={({ isActive }) => `flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] ${isActive ? 'bg-[#1F4744] text-white font-medium [&_svg]:text-amber-400' : 'hover:bg-petrol-800 hover:text-white'}`}>
            <Icon name="sliders" /><span>Configuração</span>
          </NavLink>
          <button type="button" onClick={() => { session.clear(); nav('/login') }}
            className="flex w-full items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] hover:bg-petrol-800 hover:text-white">
            <Icon name="logout" /><span>Terminar sessão</span>
          </button>
        </div>
      </nav>
      <div className="flex-[999_1_560px] min-w-0 flex flex-col">
        <header className="h-topbar flex items-center gap-3.5 px-7 bg-white border-b border-line">
          <label className="flex items-center gap-2 h-[38px] w-[440px] max-w-full px-3 border border-line rounded-[9px] bg-[#F7F8F6] text-ink-60">
            <Icon name="search" size={17} />
            <input type="search" placeholder="Pesquisar cliente, loja, colaborador ou contrato" aria-label="Pesquisa global"
              className="flex-1 min-w-0 bg-transparent outline-none text-[13.5px] text-ink placeholder:text-ink-60" />
          </label>
          <span className="flex-1" />
          <button type="button" aria-label="Notificações" className="grid place-items-center w-[38px] h-[38px] rounded-[9px] border border-line text-ink-80 hover:bg-bg"><Icon name="bell" /></button>
          {user && (
            <button type="button" onClick={() => setSenha(true)} title="Alterar a minha palavra-passe"
              className="flex items-center gap-2.5 text-[13px] leading-tight text-left rounded-lg px-1.5 py-1 hover:bg-bg">
              <Avatar nome={user.nome} size={34} />
              <div>{user.nome}<div className="text-xs text-ink-60">{PERFIL[user.perfil] ?? user.perfil}{user.perfil === 'supervisor' ? ` · ${user.zona ?? 'todas as zonas'}` : ''}</div></div>
            </button>
          )}
          {senha && <MinhaSenhaDialog onClose={() => setSenha(false)} />}
        </header>
        <main className="px-7 pt-6 pb-8 flex flex-col gap-[18px]"><Outlet /></main>
      </div>
    </div>
  )
}
