# Field Agency

Plataforma de gestão operacional para agências de field marketing: reposição, promoções, logística e equipas fixas.

**Estado: MVP, incremento 1.** Inclui:

- dados mestre;
- contratos com horas por dia da semana;
- geração automática de ocorrências;
- planeamento semanal com afetação persistente;
- ausências e substituições.

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
| Toda a alteração a contratos, linhas, afetações e turnos fica na tabela `auditoria`. | Master prompt §21 |

## Próximos incrementos (MVP B10–B15)

- Registo e validação de horas, com aceitação tácita a contar também para a remuneração (Q4 e Q5).
- Pré-faturação por área e período. Na primeira fase é só visual (Q7); depois envia para um dossier interno BO/BI do PHC.
- Apuramento de remunerações para o PHC: cliente, horas trabalhadas e valor dessas horas (Q8).
- Contador da muito curta duração (35 dias seguidos e 70 dias por ano).
- Importação inicial por Excel.
