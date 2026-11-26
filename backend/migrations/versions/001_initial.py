"""Initial schema: recipients, members, tasks, assistant interactions."""
from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this idempotent alongside create_all.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS care_recipients (
            id SERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            date_of_birth DATE,
            timezone VARCHAR(60) DEFAULT 'Asia/Kolkata',
            notes TEXT DEFAULT '',
            created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS family_members (
            id SERIAL PRIMARY KEY,
            care_recipient_id INTEGER REFERENCES care_recipients(id),
            name VARCHAR(120) NOT NULL,
            relationship VARCHAR(120) DEFAULT '',
            avatar_url VARCHAR(500),
            created_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS care_tasks (
            id SERIAL PRIMARY KEY,
            care_recipient_id INTEGER NOT NULL REFERENCES care_recipients(id),
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            task_type VARCHAR(40) DEFAULT 'other',
            due_at TIMESTAMPTZ NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            priority VARCHAR(20) DEFAULT 'normal',
            assigned_member_id INTEGER REFERENCES family_members(id),
            completed_by_member_id INTEGER REFERENCES family_members(id),
            completed_at TIMESTAMPTZ,
            version INTEGER DEFAULT 1 NOT NULL,
            created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS ix_care_tasks_status ON care_tasks (status);
        CREATE INDEX IF NOT EXISTS ix_care_tasks_due_at ON care_tasks (due_at);
        CREATE TABLE IF NOT EXISTS assistant_interactions (
            id SERIAL PRIMARY KEY,
            care_recipient_id INTEGER REFERENCES care_recipients(id),
            family_member_id INTEGER REFERENCES family_members(id),
            question TEXT NOT NULL,
            context_sent TEXT DEFAULT '',
            answer TEXT DEFAULT '',
            latency_ms INTEGER DEFAULT 0,
            model_name VARCHAR(80) DEFAULT 'template',
            created_at TIMESTAMPTZ
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS assistant_interactions;
        DROP TABLE IF EXISTS care_tasks;
        DROP TABLE IF EXISTS family_members;
        DROP TABLE IF EXISTS care_recipients;
        """
    )
