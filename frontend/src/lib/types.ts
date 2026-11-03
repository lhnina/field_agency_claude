export type IdNome = { id: number; nome: string }
export type TipoContrato = 'REP' | 'PRO' | 'LOG' | 'EQF'
export type EstadoContrato = 'proposta' | 'ativo' | 'suspenso' | 'terminado'
export type Vinculo = 'sem_termo' | 'a_termo' | 'muito_curta_duracao' | 'recibos_verdes'

export type Cliente = {
  id: number; nome: string; nif: string | null; codigo_erp: number | null; morada: string | null; codigo_postal: string | null
  localidade: string | null; telefone: string | null; email: string | null; url: string | null; contacto_nome: string | null
  gestor_conta: string | null; observacoes: string | null; ativo: boolean; marcas: (IdNome & { ativo?: boolean })[]
}

export type Loja = {
  id: number; nome: string; insignia_id: number | null; zona_id: number | null; supervisor_id: number | null
  nome_credencial: string | null; morada: string | null; codigo_postal: string | null; localidade: string | null
  horario_semana: string | null; horario_fim_semana: string | null
  contacto_nome: string | null; contacto_funcao: string | null; contacto_email: string | null; contacto_telefone: string | null
  ativo: boolean; insignia: IdNome | null; zona: IdNome | null
}

export type Colaborador = {
  id: number; numero: string; nome: string; funcao: string | null; email: string | null; telefone: string | null
  vinculo: Vinculo; data_inicio: string | null; data_fim_vinculo: string | null; zona_id: number | null
  supervisor_id: number | null; custo_hora: string; disponibilidade: string; ativo: boolean; zona: IdNome | null
  horas_afetadas: string
}

export type Afetacao = { id: number; colaborador_id: number; colaborador_nome: string; desde: string; ate: string | null }

export const DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'] as const
export type Dia = (typeof DIAS)[number]

export type Linha = {
  id: number; loja_id: number; loja_nome: string; loja_insignia: string | null; loja_zona: string | null
  inicio: string; fim: string | null; hora_inicio: string | null; preco_hora: string; preco_hora_extra: string | null
  custo_hora_especial: string | null; mecanica: string | null; observacoes: string | null
  horas_semana: string; horas_mes: string; valor_mensal: string
  afetacao_atual: Afetacao | null; afetacoes: Afetacao[]
} & Record<`h_${Dia}`, string>

export type ContratoResumo = {
  id: number; numero: string; tipo: TipoContrato; estado: EstadoContrato; cliente_id: number; cliente_nome: string
  marca_nome: string | null; descricao: string | null; evento: string | null; data: string; inicio: string; fim: string | null
  versao: number; n_linhas: number; horas_semana: string; horas_mes: string; valor_mensal: string; linhas_por_atribuir: number
}
export type Contrato = ContratoResumo & { marca_id: number | null; observacoes: string | null; linhas: Linha[] }

export type Ocorrencia = {
  id: number; data: string; data_original: string; reagendada_feriado: boolean; hora_inicio: string | null; horas: number
  estado: string; colaborador_id: number | null; colaborador_previsto_id: number | null; substituicao: boolean
  motivo: string | null; linha_id: number; contrato_id: number; contrato_numero: string; tipo: TipoContrato
  cliente: string; loja: string; loja_id: number; mecanica: string | null; alertas: string[]
}
export type LinhaColaborador = {
  id: number; nome: string; numero: string; vinculo: Vinculo; funcao: string | null; horas_semana: number
  limite_semana: number | null; alertas: string[]; ausencias: { tipo: string; inicio: string; fim: string }[]; disponibilidade: string
}
export type Planeamento = {
  inicio: string; fim: string; dias: string[]; colaboradores: LinhaColaborador[]; ocorrencias: Ocorrencia[]
  por_atribuir: Ocorrencia[]; resumo: { total: number; por_atribuir: number; conflitos: number; ausencias: number; horas: number }
}
export type Candidato = {
  colaborador_id: number; nome: string; vinculo: Vinculo; horas_dia: number; horas_semana: number; pontos: number
  motivos: string[]; alertas: string[]
}
export type Ausencia = {
  id: number; colaborador_id: number; colaborador_nome: string; tipo: string; inicio: string; fim: string
  observacoes: string | null; ocorrencias_afetadas: number; por_substituir: number
}
