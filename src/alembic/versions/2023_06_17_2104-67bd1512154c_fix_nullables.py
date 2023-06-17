"""Fix nullables

Revision ID: 67bd1512154c
Revises: e4b61dedb707
Create Date: 2023-06-17 21:04:59.216809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67bd1512154c'
down_revision = 'e4b61dedb707'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('communities') as batch_op:
        batch_op.alter_column('lemmy_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('ident', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column('nsfw', existing_type=sa.BOOLEAN(), nullable=False)

    with op.batch_alter_table('posts') as batch_op:
        batch_op.alter_column('reddit_link', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column('lemmy_link', existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column('updated', existing_type=sa.DATETIME(), nullable=False)
        batch_op.alter_column('nsfw', existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column('community_id', existing_type=sa.INTEGER(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('posts') as batch_op:
        batch_op.alter_column('community_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('nsfw', existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column('updated', existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column('lemmy_link', existing_type=sa.VARCHAR(), nullable=True)
        batch_op.alter_column('reddit_link', existing_type=sa.VARCHAR(), nullable=True)

    with op.batch_alter_table('communities') as batch_op:
        batch_op.alter_column('nsfw', existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column('ident', existing_type=sa.VARCHAR(), nullable=True)
        batch_op.alter_column('lemmy_id', existing_type=sa.INTEGER(), nullable=True)
