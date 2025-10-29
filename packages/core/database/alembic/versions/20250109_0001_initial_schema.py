"""Initial database schema for multitenant car accessories chatbot

Revision ID: 20250109_0001
Revises:
Create Date: 2025-01-09 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250109_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables and indexes."""

    # ====================
    # STEP 1: Core Tables
    # ====================

    # Tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('contacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_tenants_slug', 'tenants', ['slug'])
    op.create_index('idx_tenants_active', 'tenants', ['id'], postgresql_where=sa.text('active = true'))

    # Body Types
    op.create_table(
        'body_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name_ru', sa.String(length=100), nullable=False),
        sa.Column('name_kg', sa.String(length=100), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # Brands
    op.create_table(
        'brands',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_ru', sa.String(length=100), nullable=True),
        sa.Column('name_kg', sa.String(length=100), nullable=True),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_brands_slug', 'brands', ['slug'])

    # Product Categories
    op.create_table(
        'product_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name_ru', sa.String(length=255), nullable=False),
        sa.Column('name_kg', sa.String(length=255), nullable=True),
        sa.Column('description_ru', sa.Text(), nullable=True),
        sa.Column('description_kg', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('idx_categories_active', 'product_categories', ['id'], postgresql_where=sa.text('active = true'))

    # ====================
    # STEP 2: Dependent Tables
    # ====================

    # Models
    op.create_table(
        'models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_ru', sa.String(length=100), nullable=True),
        sa.Column('year_from', sa.Integer(), nullable=True),
        sa.Column('year_to', sa.Integer(), nullable=True),
        sa.Column('body_type_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['body_type_id'], ['body_types.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand_id', 'name', 'year_from', 'year_to', name='uq_model_brand_name_years')
    )
    op.create_index('idx_models_brand', 'models', ['brand_id'])
    op.create_index('idx_models_body_type', 'models', ['body_type_id'])

    # Product Options
    op.create_table(
        'product_options',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name_ru', sa.String(length=255), nullable=False),
        sa.Column('name_kg', sa.String(length=255), nullable=True),
        sa.Column('option_type', sa.String(length=20), nullable=False),
        sa.Column('allowed_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('applicable_to', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['product_categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_id', 'code', name='uq_option_category_code')
    )
    op.create_index('idx_options_category', 'product_options', ['category_id'])

    # Bot Texts
    op.create_table(
        'bot_texts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('text_ru', sa.Text(), nullable=False),
        sa.Column('text_kg', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'key', name='uq_bot_text_tenant_key')
    )
    op.create_index('idx_bot_texts_tenant', 'bot_texts', ['tenant_id'])

    # Patterns
    op.create_table(
        'patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('available', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['product_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'category_id', 'model_id', name='uq_pattern_tenant_category_model')
    )
    op.create_index('idx_patterns_tenant', 'patterns', ['tenant_id'])
    op.create_index('idx_patterns_model', 'patterns', ['model_id'])
    op.create_index('idx_patterns_lookup', 'patterns', ['tenant_id', 'category_id', 'model_id'])

    # Prices
    op.create_table(
        'prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('option_id', sa.Integer(), nullable=True),
        sa.Column('body_type_id', sa.Integer(), nullable=True),
        sa.Column('base_price', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='KGS', nullable=False),
        sa.Column('valid_from', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(category_id IS NOT NULL AND option_id IS NULL) OR (category_id IS NULL AND option_id IS NOT NULL)',
            name='chk_price_category_or_option'
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['product_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['option_id'], ['product_options.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['body_type_id'], ['body_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_prices_tenant', 'prices', ['tenant_id'])
    op.create_index('idx_prices_category', 'prices', ['category_id'])
    op.create_index('idx_prices_option', 'prices', ['option_id'])
    op.create_index('idx_prices_validity', 'prices', ['valid_from', 'valid_to'], postgresql_where=sa.text('valid_to IS NULL'))

    # ====================
    # STEP 3: PostgreSQL Extensions and Functions
    # ====================

    # Включаем расширение для fuzzy search
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # Создаем триграммные индексы для поиска по моделям и маркам
    op.execute('CREATE INDEX idx_brands_name_trgm ON brands USING gin(name gin_trgm_ops)')
    op.execute('CREATE INDEX idx_models_name_trgm ON models USING gin(name gin_trgm_ops)')

    # ====================
    # STEP 4: Row-Level Security (опционально, для production)
    # ====================

    # Включаем RLS для таблиц с tenant_id
    # Раскомментируйте для включения RLS
    # op.execute('ALTER TABLE patterns ENABLE ROW LEVEL SECURITY')
    # op.execute('ALTER TABLE prices ENABLE ROW LEVEL SECURITY')
    # op.execute('ALTER TABLE bot_texts ENABLE ROW LEVEL SECURITY')

    # Политика изоляции по tenant_id
    # op.execute('''
    #     CREATE POLICY tenant_isolation ON patterns
    #     FOR ALL
    #     USING (tenant_id = current_setting('app.current_tenant_id')::INTEGER)
    # ''')



def downgrade() -> None:
    """Drop all tables and indexes."""

    # Удаляем таблицы в обратном порядке (из-за FK constraints)
    op.drop_table('prices')
    op.drop_table('patterns')
    op.drop_table('bot_texts')
    op.drop_table('product_options')
    op.drop_table('models')
    op.drop_table('product_categories')
    op.drop_table('brands')
    op.drop_table('body_types')
    op.drop_table('tenants')

    # Удаляем расширения
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')
