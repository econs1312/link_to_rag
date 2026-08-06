from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def init_db():
    """Initialize database extensions, tables, triggers and backfill."""
    async with engine.begin() as conn:
        logger.info("Ensuring pgvector extension is enabled...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        logger.info("Creating database tables if not present...")
        await conn.run_sync(Base.metadata.create_all)

        # ── Full-Text Search: tsvector auto-update trigger ────────────────────
        logger.info("Ensuring tsvector column and trigger exist for full-text search...")

        # Add the column if it doesn't exist (safe for existing DBs without migration tool)
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'document_chunks' AND column_name = 'search_vector'
                ) THEN
                    ALTER TABLE document_chunks ADD COLUMN search_vector tsvector;
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector
                        ON document_chunks USING gin(search_vector);
                END IF;
            END $$;
        """))

        # Create or replace trigger function to auto-populate search_vector
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('simple', COALESCE(NEW.chunk_text, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))

        # Create trigger (DROP + CREATE to ensure it's always up-to-date)
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS trg_document_chunks_search_vector ON document_chunks;
            CREATE TRIGGER trg_document_chunks_search_vector
                BEFORE INSERT OR UPDATE OF chunk_text ON document_chunks
                FOR EACH ROW
                EXECUTE FUNCTION document_chunks_search_vector_update();
        """))

        # Backfill existing chunks that have NULL search_vector
        result = await conn.execute(text("""
            UPDATE document_chunks
            SET search_vector = to_tsvector('simple', COALESCE(chunk_text, ''))
            WHERE search_vector IS NULL;
        """))
        logger.info("tsvector backfill completed", rows_updated=result.rowcount)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
