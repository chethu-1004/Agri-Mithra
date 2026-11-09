from alembic import op
from agrinetra.database.models import Base

revision = '0005_market_contacts'
down_revision = '0004_market_product_image'
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    bind = op.get_bind()
    table = Base.metadata.tables.get('market_contacts')
    if table is not None:
        table.drop(bind=bind, checkfirst=True)

