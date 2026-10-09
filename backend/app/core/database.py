import logging
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Check if using sqlite or postgresql
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable foreign keys on SQLite connections
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_database_triggers(target_engine=None):
    """
    Applies the DB trigger that blocks UPDATE and DELETE on timeline_events,
    enforcing Hard Constraint 8 (Append-only timeline events).
    Works on both PostgreSQL and SQLite engines.
    """
    eng = target_engine or engine
    dialect = eng.dialect.name

    with eng.connect() as conn:
        with conn.begin():
            if dialect == "postgresql":
                # Ensure pgvector extension is available in Postgres
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                except Exception as e:
                    logger.warning(f"Could not create pgvector extension: {e}")

                conn.execute(
                    text(
                        """
                        CREATE OR REPLACE FUNCTION block_timeline_mutation()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            RAISE EXCEPTION 'timeline_events is append-only. UPDATE and DELETE operations are forbidden.';
                        END;
                        $$ LANGUAGE plpgsql;
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        DROP TRIGGER IF EXISTS trg_timeline_events_no_update ON timeline_events;
                        CREATE TRIGGER trg_timeline_events_no_update
                        BEFORE UPDATE ON timeline_events
                        FOR EACH ROW EXECUTE FUNCTION block_timeline_mutation();
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        DROP TRIGGER IF EXISTS trg_timeline_events_no_delete ON timeline_events;
                        CREATE TRIGGER trg_timeline_events_no_delete
                        BEFORE DELETE ON timeline_events
                        FOR EACH ROW EXECUTE FUNCTION block_timeline_mutation();
                        """
                    )
                )
            elif dialect == "sqlite":
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_timeline_events_no_update
                        BEFORE UPDATE ON timeline_events
                        BEGIN
                            SELECT RAISE(ABORT, 'timeline_events is append-only. UPDATE operations are forbidden.');
                        END;
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_timeline_events_no_delete
                        BEFORE DELETE ON timeline_events
                        BEGIN
                            SELECT RAISE(ABORT, 'timeline_events is append-only. DELETE operations are forbidden.');
                        END;
                        """
                    )
                )
