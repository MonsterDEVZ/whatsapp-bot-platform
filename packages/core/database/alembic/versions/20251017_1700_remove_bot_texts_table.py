"""Remove bot_texts table

Revision ID: 20251017_1700
Revises: 20251009_1350_e5acffa65eb0
Create Date: 2025-10-17 17:00:00.000000

Description:
    Удаляет таблицу bot_texts, так как все тексты интерфейса теперь
    хранятся в JSON файлах locales/*.json.

    Таблица bot_texts была устаревшей и не использовалась в коде.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251017_1700'
down_revision: Union[str, None] = '20251009_1350_e5acffa65eb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Удаляет таблицу bot_texts.
    """
    # Удаляем таблицу bot_texts
    op.drop_table('bot_texts')


def downgrade() -> None:
    """
    Восстанавливает таблицу bot_texts (на случай отката).
    """
    # Создаем таблицу bot_texts
    op.create_table('bot_texts',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('text_ru', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('text_kg', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='bot_texts_tenant_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='bot_texts_pkey'),
        sa.UniqueConstraint('tenant_id', 'key', name='uq_bot_text_tenant_key')
    )

    # Восстанавливаем индекс
    op.create_index('idx_bot_texts_tenant', 'bot_texts', ['tenant_id'], unique=False)
