# Field Agency

Plataforma de gestão operacional para agências de field marketing: reposição, promoções, logística e equipas fixas.

**Estado: MVP concluído (incrementos 1 a 3).** Inclui:

- dados mestre;
- contratos com horas por dia da semana;
- geração automática de ocorrências;
- planeamento semanal com afetação persistente;
- ausências e substituições;
- execução e validação de horas, com aceitação tácita;
- pré-faturação por área e mês;
- apuramento de remunerações com exportação CSV para o PHC;
- fecho e reabertura de períodos;
- contador da muito curta duração;
- importação inicial por Excel de clientes, lojas, colaboradores e contratos (menu **Importar dados**).

Referências:

- Análise e conceção: <https://claude.ai/artifact/LP4ySFBDgxH1GDaUpUAkF3>
- Design aprovado (proposta visual A e os 5 ecrãs): <https://claude.ai/artifact/9y9hznFBjnj6xJTKm3jUo1>

## Arranque rápido (Docker)

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api python -m app.seed   # dados de demonstração
```

Depois abra <http://localhost:8080>. A API e a documentação OpenAPI ficam em <http://localhost:8000/docs>.

Todos os utilizadores de demonstração usam a palavra-passe `demo1234`:

| Email | Perfil |
| --- | --- |
| hugo@promovida.pt | Gestor operacional |
| marta@promovida.pt | Direção |
| rui@promovida.pt / sara@promovida.pt | Supervisores; só veem a sua equipa |
| admin@promovida.pt | Administrador |

## Desenvolvimento sem Docker

```bash
# backend (Python 3.12 ou superior, PostgreSQL 16)
cd backend
pip install -r requirements.txt
export FA_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/fieldagency
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev        # http://localhost:5173 (encaminha /api para :8000)
```

Para correr os testes, é preciso uma base de dados `fieldagency_test`. A variável `FA_DATABASE_URL` define-se no `tests/conftest.py`:

```bash
cd backend && pytest
```

## Estrutura

```
backend/
  app/models.py            modelo de dados (Contrato → LinhaContrato → Ocorrencia; Afetacao; Ausencia; Feriado; Auditoria)
  app/services/operacao.py regras de negócio (geração, feriados, afetação, substituição, candidatos, vista semanal)
  app/api/                 endpoints REST (auth, dados mestre, colaboradores, ausências, contratos, planeamento)
  alembic/                 migrações versionadas
  tests/                   testes unitários e de API
frontend/
  src/design/tokens.json   tokens do design aprovado (também em tailwind.config.js)
  src/components/          Layout e biblioteca de componentes (Button, Badge, Card, Seg, Modal…)
  src/pages/               Dashboard, Planeamento, Contratos, Contrato, Colaboradores, Clientes e lojas, Ausências
```

## Regras de negócio implementadas

| Regra | Origem |
| --- | --- |
| Faturação por horas **contratadas**. As executadas servem para apurar o custo. | Q1 |
| As horas de cada linha são definidas por dia da semana (Seg a Dom). | Q2 |
| Horas/mês = horas/semana × 52 ÷ 12. Valor mensal = horas/mês × preço/hora. | Q3 |
| O custo/hora vem da ficha do colaborador; cada linha pode ter um custo especial. | Q6 |
| Feriado: o serviço passa para outro dia, de preferência o próximo dia útil da mesma semana sem horas nessa linha. | Q9 |
| Limites de 8 h/dia e 40 h/semana, sem IRCT aplicável. São alertas e não bloqueiam. Não se aplicam a recibos verdes. | Q15, Q16 |
| A afetação é **persistente**: o colaborador fica na loja até ao fim do contrato. | Master prompt §7 |
| A substituição altera só aquele turno. O histórico guarda o colaborador previsto e o efetivo. | Master prompt §12 |
| O supervisor só vê e altera a sua equipa e as lojas a seu cargo. | Master prompt §12 e §20 |
| Toda a alteração a contratos, linhas, afetações, turnos, validações e fechos fica na tabela `auditoria`. | Master prompt §21 |
| Aceitação tácita: um serviço passado, sem registo, conta com as horas planeadas, também para remuneração. Desliga-se por organização. | Q4 |
| O supervisor (só a sua equipa) e o gestor validam. Corrigir horas já validadas exige motivo e obriga a nova validação. | Q5 |
| Um serviço rejeitado conta com 0 horas de custo e de remuneração; a faturação de Reposição não muda. | Q1 |
| Pré-faturação de Reposição: h/semana × 52 ÷ 12 × preço, em proporção dos dias de vigência no mês. Promoções: horas planeadas da campanha no mês. As linhas sem colaborador também são faturadas. Nesta fase é só para consulta. | Q1, Q3, Q7 |
| Encargos sociais: uma percentagem por tipo de vínculo (em **Configuração**) soma-se ao custo/hora nos custos e margens. O apuramento salarial usa o valor sem encargos. | Decisão de 2 nov 2026 |
| Apuramento: horas validadas × custo/hora do colaborador (ou custo especial da linha), por colaborador e cliente. Os prestadores aparecem separados. CSV com `;`, decimais com vírgula e UTF-8. | Q6, Q8 |
| Fecho mensal: a faturação fecha por área e a remuneração fecha o mês inteiro, que só fecha sem serviços por validar. Depois do fecho, nada desse mês se altera. Só a Direção ou o Administrador reabrem. | R10, R11 |
| Muito curta duração: alerta a partir de 56 de 70 dias no ano e de 28 de 35 dias seguidos; erro quando se excede. | Código do Trabalho, art. 142.º |

## Importação inicial (Excel)

Em **Importar dados**, importe por esta ordem:

1. clientes;
2. lojas;
3. colaboradores;
4. contratos.

Para cada tipo:

- Descarregue o modelo, que traz uma linha de exemplo e uma folha de instruções.
- Carregue o ficheiro preenchido e veja a pré-visualização, com os erros e avisos de cada linha.
- Importe. Só é possível importar quando não houver erros, e a importação grava tudo de uma vez.

Clientes, lojas e colaboradores que já existem são atualizados; as células vazias não apagam valores. Os contratos são sempre criados de novo: as linhas com a mesma "Referência" formam um contrato. Contratos ativos geram logo o planeamento.

## Próximos passos

- Documentação com validades (B17) e alertas no planeamento.
- App do colaborador (PWA): escala, confirmação e registo de horas (B18). Passa a alimentar a origem "registo" na validação.
- Envio da pré-faturação para o PHC, como dossier interno BO/BI com detalhe por loja (Q7, fase 2).
