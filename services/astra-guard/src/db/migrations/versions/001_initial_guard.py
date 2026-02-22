"""initial_guard_schema

Revision ID: 001_guard
Revises: 
Create Date: 2026-02-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_guard'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 1. Tabla Snapshots
    op.create_table(
        'snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('artifact_url', sa.String(), nullable=False),
        sa.Column('s3_version_id', sa.String(), nullable=False),
        sa.Column('root_hash', sa.String(64), nullable=False),
        sa.Column('algorithm', sa.Enum('SHA256', 'SHA512', name='hashalgorithm'), nullable=True),
        sa.Column('kms_key_id', sa.String(), nullable=False),
        sa.Column('encrypted_data_key', sa.String(), nullable=False),
        sa.Column('parent_snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('snapshots.id'), nullable=True),
        sa.Column('version_number', sa.Integer(), default=1),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_snapshots_tenant_id'), 'snapshots', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_snapshots_root_hash'), 'snapshots', ['root_hash'], unique=False)

    # 2. Tabla Merkle Trees
    op.create_table(
        'merkle_trees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('snapshots.id'), unique=True),
        sa.Column('tree_structure', postgresql.JSONB, nullable=False),
    )

    # 3. Tabla Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('snapshots.id'), nullable=True),
        sa.Column('actor_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)

def downgrade():
    op.drop_table('audit_logs')
    op.drop_table('merkle_trees')
    op.drop_table('snapshots')
    op.execute('DROP TYPE hashalgorithm')
