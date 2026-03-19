"""Sequential ID generator with SELECT FOR UPDATE to prevent race conditions."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def generate_code(db: Session, prefix: str, table_name: str, code_col: str) -> str:
    """Thread-safe sequential code generator.

    Uses advisory lock to prevent race conditions when two users submit
    simultaneously. Compatible with Supabase connection pooler.

    Returns: next sequential code e.g. "ANG-001", "CPY-042", "CMB-001"
    """
    # Use pg_advisory_xact_lock with a hash of the table name for safe locking
    lock_id = hash(table_name) % (2**31)
    db.execute(text(f"SELECT pg_advisory_xact_lock({lock_id})"))

    result = db.execute(
        text(f"SELECT MAX({code_col}) FROM {table_name}")
    ).scalar()

    if result is None:
        next_num = 1
    else:
        try:
            next_num = int(result.split("-")[1]) + 1
        except (IndexError, ValueError):
            logger.warning("Could not parse code '%s', starting from 1", result)
            next_num = 1

    code = f"{prefix}-{next_num:03d}"
    logger.info("Generated %s code: %s", prefix, code)
    return code
