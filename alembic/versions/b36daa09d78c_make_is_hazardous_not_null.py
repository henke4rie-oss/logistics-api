"""make is_hazardous not null

Revision ID: b36daa09d78c
Revises: 02ea6f792b40
Create Date: 2026-11-03 15:09:57.013904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b36daa09d78c'
down_revision: Union[str, Sequence[str], None] = '02ea6f792b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    manifests = sa.table("manifests", sa.column("is_hazardous", sa.Boolean))
    # Update existing rows where is_hazardous is NULL to False
    op.execute(manifests.update().where(manifests.c.is_hazardous == (None)).values(is_hazardous=False))
    with op.batch_alter_table("manifests") as batch_op:
        batch_op.alter_column("is_hazardous", existing_type=sa.Boolean, nullable=False, server_default=sa.false())


def downgrade() -> None:
    with op.batch_alter_table("manifests") as batch_op:
        batch_op.alter_column("is_hazardous", existing_type=sa.Boolean, nullable=True, server_default=None)
