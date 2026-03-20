"""add_gene_source_registry_and_template_items

Revision ID: ee3067b5a373
Revises: c4a1f2b89d03
Create Date: 2026-03-20 15:30:59.069134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ee3067b5a373'
down_revision: Union[str, Sequence[str], None] = 'c4a1f2b89d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'template_items',
        sa.Column('template_id', sa.String(length=36), sa.ForeignKey('instance_templates.id'), nullable=False),
        sa.Column('item_type', sa.String(length=16), nullable=False),
        sa.Column('item_slug', sa.String(length=128), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_template_items_template_id', 'template_items', ['template_id'])
    op.create_index('ix_template_items_deleted_at', 'template_items', ['deleted_at'])
    op.create_index(
        'uq_template_item_active', 'template_items',
        ['template_id', 'item_type', 'item_slug'],
        unique=True, postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.add_column('genes', sa.Column('source_registry', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('genes', 'source_registry')
    op.drop_index('uq_template_item_active', table_name='template_items')
    op.drop_index('ix_template_items_deleted_at', table_name='template_items')
    op.drop_index('ix_template_items_template_id', table_name='template_items')
    op.drop_table('template_items')
