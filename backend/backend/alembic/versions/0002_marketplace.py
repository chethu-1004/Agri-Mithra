from alembic import op
from agrinetra.database.models import Base

revision = '0002_marketplace'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # The initial migration uses Base.metadata.create_all, so create_all is
    # deliberately idempotent for both existing installs and fresh databases.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    bind = op.get_bind()
    for table in ('market_orders', 'market_listings', 'market_products'):
        if table in Base.metadata.tables:
            Base.metadata.tables[table].drop(bind=bind, checkfirst=True)
