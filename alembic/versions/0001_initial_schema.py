"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-07-17

Creates the `links` table with columns:
  - code        VARCHAR(6)  PRIMARY KEY
  - original_url VARCHAR(2048) NOT NULL
  - created_at  TIMESTAMPTZ NOT NULL
  - click_count INTEGER NOT NULL DEFAULT 0
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "links",
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(op.f("ix_links_code"), "links", ["code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_links_code"), table_name="links")
    op.drop_table("links")
