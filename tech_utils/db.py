import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
load_dotenv()

from tech_utils.logger import init_logger
logger = init_logger("TechUtils_DB")

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
}

def get_conn():
    """Create a new connection to the PostgreSQL database using environment config."""
    return psycopg2.connect(**DB_CONFIG)


def update_versioned(
    conn,
    table: str,
    key_fields: dict,
    update_fields: dict,
):
    """
    Perform a versioned update on a table:
    - Close the current active record (set `valid_to`)
    - Copy the latest row and apply updates
    - Insert the new version with updated fields and current timestamp

    Args:
        conn: Active psycopg2 connection
        table (str): Table name
        key_fields (dict): Dict of primary key fields to locate the current row
        update_fields (dict): Fields to update in the new version
    """
    now = datetime.now(timezone.utc)

    # WHERE clause setup for key fields
    where_clauses = [f"{field} = %s" for field in key_fields]
    where_sql = " AND ".join(where_clauses)
    key_values = list(key_fields.values())

    # Step 1: Close the current active version (if any)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {table}
                SET valid_to = %s
                WHERE {where_sql} AND valid_to IS NULL
                """,
                [now] + key_values,
            )
    except psycopg2.errors.UndefinedTable as e:
        raise RuntimeError(f"Table '{table}' not found: {e}")
    except psycopg2.errors.UndefinedColumn as e:
        raise RuntimeError(f"Column not found: {e}")

    # Step 2: Retrieve the most recent version (latest valid_from)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM {table}
            WHERE {where_sql}
            ORDER BY valid_from DESC
            LIMIT 1
            """,
            key_values,
        )
        last_row = cur.fetchone()
        if not last_row:
            logger.warning(f"Update-versioned {table}: No existing row found for {key_fields}")
            return
        desc = [d.name for d in cur.description]

    # Step 3: Construct the new row
    new_row = dict(zip(desc, last_row))
    new_row.update(update_fields)
    new_row["valid_from"] = now
    new_row["valid_to"] = None
    new_row.pop("id", None)  # ID is typically auto-incremented

    # INSERT new versioned row
    columns = ', '.join(new_row.keys())
    placeholders = ', '.join(['%s'] * len(new_row))
    values = list(new_row.values())

    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
            """,
            values
        )

    conn.commit()
