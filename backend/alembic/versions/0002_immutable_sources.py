"""Protect immutable sources and revision/audit history in PostgreSQL."""

from alembic import op

revision = "0002_immutable_sources"
down_revision = "7c645ad3a9e8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION intakeflow_immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable history cannot be updated or deleted'; END $$""")
    for table in [
        "request_messages",
        "ai_extraction_revisions",
        "reviewed_draft_revisions",
        "field_corrections",
        "audit_events",
    ]:
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION intakeflow_immutable_row()"
        )
    op.execute("""CREATE FUNCTION intakeflow_immutable_source() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.original_message IS DISTINCT FROM OLD.original_message
      OR NEW.title IS DISTINCT FROM OLD.title OR NEW.org_id IS DISTINCT FROM OLD.org_id
      OR NEW.unit_id IS DISTINCT FROM OLD.unit_id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
      OR NEW.thread_id IS DISTINCT FROM OLD.thread_id THEN
        RAISE EXCEPTION 'original request and trusted ownership are immutable';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER immutable_source BEFORE UPDATE ON maintenance_requests FOR EACH ROW EXECUTE FUNCTION intakeflow_immutable_source()"
    )


def downgrade():
    op.execute("DROP TRIGGER immutable_source ON maintenance_requests")
    op.execute("DROP FUNCTION intakeflow_immutable_source()")
    for table in [
        "request_messages",
        "ai_extraction_revisions",
        "reviewed_draft_revisions",
        "field_corrections",
        "audit_events",
    ]:
        op.execute(f"DROP TRIGGER immutable_history ON {table}")
    op.execute("DROP FUNCTION intakeflow_immutable_row()")
