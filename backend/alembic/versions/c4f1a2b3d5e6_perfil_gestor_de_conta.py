"""perfil gestor de conta, cliente.gestor_conta_id e zona do supervisor

Revision ID: c4f1a2b3d5e6
Revises: ac7356accbb4
Create Date: 2026-11-03 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f1a2b3d5e6'
down_revision: Union[str, Sequence[str], None] = 'ac7356accbb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE perfil ADD VALUE IF NOT EXISTS 'gestor_conta'")
    op.add_column('clientes', sa.Column('gestor_conta_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_clientes_gestor_conta_id_users', 'clientes', 'users', ['gestor_conta_id'], ['id'])
    op.create_index('ix_clientes_gestor_conta_id', 'clientes', ['gestor_conta_id'])
    # O texto livre anterior passa para a ligação ao utilizador quando o nome ou email coincide.
    op.execute("""
        UPDATE clientes c SET gestor_conta_id = u.id FROM users u
        WHERE u.tenant_id = c.tenant_id AND c.gestor_conta IS NOT NULL
          AND (lower(trim(c.gestor_conta)) = lower(u.nome) OR lower(trim(c.gestor_conta)) = lower(u.email))
    """)
    op.drop_column('clientes', 'gestor_conta')
    # Supervisor: zona que supervisiona (vazio = todas)
    op.add_column('users', sa.Column('zona_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_zona_id_zonas', 'users', 'zonas', ['zona_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_users_zona_id_zonas', 'users', type_='foreignkey')
    op.drop_column('users', 'zona_id')
    op.add_column('clientes', sa.Column('gestor_conta', sa.String(120), nullable=True))
    op.execute("UPDATE clientes c SET gestor_conta = u.nome FROM users u WHERE u.id = c.gestor_conta_id")
    op.drop_index('ix_clientes_gestor_conta_id', 'clientes')
    op.drop_constraint('fk_clientes_gestor_conta_id_users', 'clientes', type_='foreignkey')
    op.drop_column('clientes', 'gestor_conta_id')
