import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import Layout from './components/Layout'
import { ToastProvider } from './components/ui'
import { session } from './lib/api'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Planeamento from './pages/Planeamento'
import Contratos from './pages/Contratos'
import ContratoDetalhe from './pages/ContratoDetalhe'
import Colaboradores from './pages/Colaboradores'
import ClientesLojas from './pages/ClientesLojas'
import Ausencias from './pages/Ausencias'
import Validacao from './pages/Validacao'
import PreFaturacao from './pages/PreFaturacao'
import Apuramentos from './pages/Apuramentos'
import Importacao from './pages/Importacao'
import Configuracao from './pages/Configuracao'
import type { ReactNode } from 'react'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 } } })

function Privado({ children }: { children: ReactNode }) {
  return session.token() ? <>{children}</> : <Navigate to="/login" replace />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Privado><Layout /></Privado>}>
              <Route index element={<Dashboard />} />
              <Route path="planeamento" element={<Planeamento />} />
              <Route path="ausencias" element={<Ausencias />} />
              <Route path="contratos" element={<Contratos />} />
              <Route path="contratos/:id" element={<ContratoDetalhe />} />
              <Route path="colaboradores" element={<Colaboradores />} />
              <Route path="clientes" element={<ClientesLojas />} />
              <Route path="validacao" element={<Validacao />} />
              <Route path="prefaturacao" element={<PreFaturacao />} />
              <Route path="apuramentos" element={<Apuramentos />} />
              <Route path="importacao" element={<Importacao />} />
              <Route path="configuracao" element={<Configuracao />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
)
