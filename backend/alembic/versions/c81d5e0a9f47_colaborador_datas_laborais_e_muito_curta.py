"""Colaborador: datas laborais e "muito curta duração" como tipo de contrato (deixa de ser vínculo)

Preserva os dados: quem tinha o vínculo "muito curta duração" passa a "a termo" com a
caixa "Muito curta duração" assinalada; a data de admissão começa igual à data de início.

Revision ID: c81d5e0a9f47
Revises: b3cfe1bd02a8
Create Date: 2026-11-03 19:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c81d5e0a9f47'
down_revision: Union[str, Sequence[str], None] = 'b3cfe1bd02a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('colaboradores', sa.Column('muito_curta_duracao', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('colaboradores', sa.Column('data_admissao', sa.Date(), nullable=True))
    op.add_column('colaboradores', sa.Column('data_saida', sa.Date(), nullable=True))
    op.execute("UPDATE colaboradores SET muito_curta_duracao = true, vinculo = 'a_termo' WHERE vinculo = 'muito_curta_duracao'")
    op.execute("UPDATE colaboradores SET data_admissao = data_inicio WHERE data_admissao IS NULL AND vinculo <> 'recibos_verdes'")
    # retira o valor do tipo enumerado
    op.execute("ALTER TYPE tipo_vinculo RENAME TO tipo_vinculo_old")
    op.execute("CREATE TYPE tipo_vinculo AS ENUM ('sem_termo', 'a_termo', 'recibos_verdes')")
    op.execute("ALTER TABLE colaboradores ALTER COLUMN vinculo TYPE tipo_vinculo USING vinculo::text::tipo_vinculo")
    op.execute("DROP TYPE tipo_vinculo_old")


def downgrade() -> None:
    op.execute("ALTER TYPE tipo_vinculo ADD VALUE IF NOT EXISTS 'muito_curta_duracao'")
    op.execute("COMMIT")
    op.execute("UPDATE colaboradores SET vinculo = 'muito_curta_duracao' WHERE muito_curta_duracao")
    op.drop_column('colaboradores', 'data_saida')
    op.drop_column('colaboradores', 'data_admissao')
    op.drop_column('colaboradores', 'muito_curta_duracao')
