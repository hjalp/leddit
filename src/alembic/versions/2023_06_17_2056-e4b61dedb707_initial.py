"""Initial

Revision ID: 6ed17f8c445b
Revises: 
Create Date: 2023-06-17 20:56:46.087898

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4b61dedb707'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('communities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lemmy_id', sa.Integer(), nullable=True),
    sa.Column('ident', sa.String(), nullable=True),
    sa.Column('nsfw', sa.Boolean(), nullable=True),
    sa.Column('last_scrape', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reddit_link', sa.String(), nullable=True),
    sa.Column('lemmy_link', sa.String(), nullable=True),
    sa.Column('updated', sa.DateTime(), nullable=True),
    sa.Column('nsfw', sa.Boolean(), nullable=True),
    sa.Column('community_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('posts')
    op.drop_table('communities')
