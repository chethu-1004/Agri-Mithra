from alembic import op
import sqlalchemy as sa

revision = '0004_market_product_image'
down_revision = '0003_user_profile_image'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'market_products' not in sa.inspect(bind).get_table_names():
        return
    columns = {column['name'] for column in sa.inspect(bind).get_columns('market_products')}
    if 'image_storage_key' not in columns:
        op.add_column('market_products', sa.Column('image_storage_key', sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    if 'market_products' not in sa.inspect(bind).get_table_names():
        return
    columns = {column['name'] for column in sa.inspect(bind).get_columns('market_products')}
    if 'image_storage_key' in columns:
        op.drop_column('market_products', 'image_storage_key')
