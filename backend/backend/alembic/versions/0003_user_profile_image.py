from alembic import op
import sqlalchemy as sa

revision = '0003_user_profile_image'
down_revision = '0002_marketplace'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    if 'profile_image' not in columns:
        op.add_column('users', sa.Column('profile_image', sa.String(length=1024), nullable=True))


def downgrade():
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    if 'profile_image' in columns:
        op.drop_column('users', 'profile_image')
