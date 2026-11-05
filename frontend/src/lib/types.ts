export type IdNome = { id: number; nome: string }
export type TipoContrato = 'REP' | 'PRO' | 'LOG' | 'EQF'
export type EstadoContrato = 'proposta' | 'ativo' | 'suspenso' | 'terminado'
export type Vinculo = 'sem_termo' | 'a_termo' | 'recibos_verdes'

export type Cliente = {
  id: number; nome: string; nif: string | null; codigo_erp: number | null; morada: string | null; codigo_postal: string | null
  localidade: string | null; telefone: string | null; email: string | null; url: string | null; contacto_nome: string | null
  gestor_conta_id: number | null; gestor_conta: IdNome | null; observacoes: string | null; ativo: boolean; marcas: (IdNome & { ativo?: boolean })[]
}

export type Loja = {
  id: number; nome: string; insignia_id: number | null; zona_id: number | null; supervisor_id: number | null
  nome_credencial: string | null; morada: string | null; codigo_postal: string | null; localidade: string | null
  horario_semana: string | null; horario_fim_semana: string | null
  contacto_nome: string | null; contacto_funcao: string | null; contacto_email: string | null; contacto_telefone: string | null
  ativo: boolean; insignia: (IdNome & { logo_v: number | null }) | null; zona: IdNome | null; codigo_erp: string | null
}

export type Colaborador = {
  id: number; numero: string; nome: string; funcao: string | null; email: string | null; telefone: string | null
  vinculo: Vinculo; muito_curta_duracao: boolean; data_admissao: string | null; data_saida: string | null
  data_inicio: string | null; data_fim_vinculo: string | null; zona_id: number | null
  supervisor_id: number | null; custo_hora: string; disponibilidade: string; ativo: boolean; zona: IdNome | null
  horas_afetadas: string; aviso?: string | null
  data_nascimento: string | null; numero_identificacao: string | null; niss: string | null
}

export type Afetacao = { id: number; colaborador_id: number; colaborador_nome: string; desde: string; ate: string | null }

export const DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'] as const
export type Dia = (typeof DIAS)[number]

export type Linha = {
  id: number; loja_id: number; loja_nome: string; loja_insignia: string | null; loja_insignia_id: number | null; loja_insignia_logo_v: number | null; loja_zona: string | null
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
export type Contrato = ContratoResumo & {
  marca_id: number | null; observacoes: string | null; linhas: Linha[]
  valor_gestao: string | null; acrescimo_despesas_pct: string
}

// Equipas Fixas
export type RotaEquipa = { id: number; nome: string; observacoes: string | null; ativo: boolean; lojas: { id: number; nome: string; localidade: string | null }[] }
export type DiaEscala = { dia: number; rota_id: number; rota?: string; hora_inicio: string; hora_fim: string; pausa_min: number; horas?: number }
export type ElementoEquipa = {
  id: number; colaborador_id: number; colaborador: string; numero: string; funcao: string | null; desde: string; ate: string | null
  valor_gestao: number | null; valor_gestao_efetivo: number; observacoes: string | null; ativo: boolean; horas_semana: number
  custo_hora: number; escala: DiaEscala[]
}
export type Equipa = {
  rotas: RotaEquipa[]; elementos: ElementoEquipa[]; valor_gestao: number | null; acrescimo_despesas_pct: number
  resumo: { elementos: number; horas_semana: number; horas_mes: number; gestao_mensal: number; sem_escala: number }
}
export type EstadoDiaEquipa = 'planeado' | 'validado' | 'falta' | 'cancelado'
export type DiaEquipa = {
  id: number; contrato_id: number; contrato_numero: string; cliente: string; elemento_id: number; titular_id: number; titular: string
  colaborador_id: number; colaborador: string; substituicao: boolean; rota_id: number | null; rota: string | null; lojas: string[]
  data: string; hora_inicio: string; hora_fim: string; pausa_min: number; horas_planeadas: number; horas_reais: number | null
  estado: EstadoDiaEquipa; alterado: boolean; observacao: string | null; alertas: string[]
}
export type DespesaEquipa = {
  id: number; data: string; tipo: string; tipo_label: string; descricao: string | null; valor: number
  elemento_id: number | null; colaborador: string | null; refaturar: boolean
}

export type Ocorrencia = {
  id: number; data: string; data_original: string; reagendada_feriado: boolean; hora_inicio: string | null; horas: number
  estado: string; colaborador_id: number | null; colaborador_previsto_id: number | null; substituicao: boolean
  motivo: string | null; linha_id: number; contrato_id: number; contrato_numero: string; tipo: TipoContrato
  cliente: string; loja: string; loja_id: number; mecanica: string | null; alertas: string[]; documentacao?: string[]
}
export type LinhaColaborador = {
  id: number; nome: string; numero: string; vinculo: Vinculo; muito_curta_duracao?: boolean; funcao: string | null; horas_semana: number
  limite_semana: number | null; alertas: string[]; ausencias: { tipo: string; inicio: string; fim: string }[]; disponibilidade: string
}
export type Planeamento = {
  inicio: string; fim: string; dias: string[]; colaboradores: LinhaColaborador[]; ocorrencias: Ocorrencia[]
  por_atribuir: Ocorrencia[]; resumo: { total: number; por_atribuir: number; conflitos: number; ausencias: number; horas: number; documentacao?: number }
}
export type Candidato = {
  colaborador_id: number; nome: string; vinculo: Vinculo; muito_curta_duracao?: boolean; horas_dia: number; horas_semana: number; pontos: number
  motivos: string[]; alertas: string[]
}
export type Ausencia = {
  id: number; colaborador_id: number; colaborador_nome: string; tipo: string; inicio: string; fim: string
  observacoes: string | null; ocorrencias_afetadas: number; por_substituir: number
}

// ---------------------------------------------------------------- documentação
export type EstadoDocumento = 'valido' | 'a_expirar' | 'expirado' | 'em_falta'
export type TipoDocumento = { id: number; nome: string; tem_validade: boolean; dias_aviso: number; ativo: boolean; requisitos: number; documentos: number }
export type Requisito = {
  id: number; tipo_documento_id: number; tipo: string; funcao: string | null; cliente_id: number | null; cliente: string | null
  insignia_id: number | null; insignia: string | null; aplica_se: string; ativo: boolean
}
export type DocumentoReg = {
  id: number; colaborador_id: number; tipo_documento_id: number; numero: string | null; emissao: string | null; validade: string | null
  observacoes: string | null; atual: boolean; ficheiro_nome: string | null; ficheiro_tamanho: number | null; registado_em: string | null; tipo?: string
}
export type SituacaoDoc = {
  colaborador_id: number; colaborador: string; numero_colaborador: string; funcao: string | null; zona: string | null
  tipo_documento_id: number; tipo: string; tem_validade: boolean; obrigatorio: boolean; motivo: string | null
  estado: EstadoDocumento; documento: DocumentoReg | null
}
export type ResumoDoc = { expirados: number; em_falta: number; a_expirar: number; validos: number; colaboradores_com_problemas: number }

export type EstadoCredencial = 'emitida' | 'substituida' | 'anulada'
export type CredencialT = {
  id: number; numero: string; colaborador_id: number; colaborador: string; colaborador_numero: string; loja_id: number; loja: string
  cliente_id: number; cliente: string; linha_id: number | null; emitida_em: string; valida_ate: string | null; estado: EstadoCredencial
  substitui: string | null; motivo: string | null; modelo: string; ficheiro_nome: string
}
export type ModeloCredencialT = {
  id: number; nome: string; versao: number; atual: boolean; ativo: boolean; notas: string | null; cliente_id: number | null
  cliente: string | null; ficheiro_nome: string; ficheiro_tamanho: number; criado_em: string | null; criado_por: string | null
}
export type PrepararCredencial = {
  colaborador: string; loja: string; cliente: string; contrato: string; modelo: { id: number; nome: string; versao: number } | null
  modelos: { id: number; nome: string; versao: number; cliente: boolean }[]; aviso_modelo: string | null; validade: string
  data_exame_medico: string | null; em_falta: string[]; substituiveis: CredencialT[]
}

export type EstadoServicoLog = 'planeado' | 'atribuido' | 'executado' | 'validado' | 'cancelado'
export type TipoServicoLog = 'entrega' | 'recolha' | 'implementacao' | 'entrega_implementacao' | 'desmontagem'
export type CustosLog = { km: number; custo_km: number; horas: number; mao_obra: number; portagens: number; outros: number; total: number }
export type ServicoLog = {
  id: number; contrato_id: number; contrato_numero: string; cliente_id: number; cliente: string; marca: string | null
  loja_id: number; loja: string; loja_morada: string; loja_zona: string | null; insignia_id: number | null; insignia: string | null; insignia_logo_v: number | null
  tipo: TipoServicoLog; tipo_label: string; data: string; hora_inicio: string | null; hora_fim: string | null; origem: string | null
  materiais: string | null; preco: number; referencia_erp: string | null; observacoes: string | null; estado: EstadoServicoLog
  viatura_id: number | null; viatura: string | null; colaborador_id: number | null; colaborador: string | null
  ajudante_id: number | null; ajudante: string | null; km_partida: number | null; km_chegada: number | null
  portagens: number | null; outros_custos: number | null; outros_custos_desc: string | null; inicio_real: string | null; fim_real: string | null
  observacao_execucao: string | null; comprovativo_nome: string | null; motivo: string | null
  custos: CustosLog | null; margem: number | null; alertas: string[]
}
export type Viatura = { id: number; matricula: string; descricao: string | null; custo_km: number; observacoes: string | null; ativo: boolean; servicos: number }
