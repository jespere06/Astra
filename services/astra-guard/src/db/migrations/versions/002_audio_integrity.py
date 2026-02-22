"""audio_integrity_schema

Revision ID: 002_audio
Revises: 001_guard
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_audio'
down_revision = '001_guard'
branch_labels = None
depends_on = None

def upgrade():
    # Agregar columnas para la evidencia de audio
    op.add_column('snapshots', sa.Column('audio_url', sa.String(), nullable=True))
    op.add_column('snapshots', sa.Column('audio_hash', sa.String(64), nullable=True))
    op.add_column('snapshots', sa.Column('audio_s3_version', sa.String(), nullable=True))
    
    # Índice para búsquedas forenses por hash de audio
    op.create_index(op.f('ix_snapshots_audio_hash'), 'snapshots', ['audio_hash'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_snapshots_audio_hash'), table_name='snapshots')
    op.drop_column('snapshots', 'audio_s3_version')
    op.drop_column('snapshots', 'audio_hash')
    op.drop_column('snapshots', 'audio_url')
