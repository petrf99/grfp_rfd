import pytest
import psycopg2
from datetime import datetime, timezone
from tech_utils.db import get_conn, update_versioned

TEST_TABLE = "test_versioned_table"

@pytest.fixture(scope="module")
def setup_test_table():
    """Fixture to set up and tear down a test table for versioning tests."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"""
            DROP TABLE IF EXISTS {TEST_TABLE};
            CREATE TABLE {TEST_TABLE} (
                id SERIAL PRIMARY KEY,
                key_field TEXT,
                value_field TEXT,
                valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                valid_to TIMESTAMPTZ DEFAULT NULL
            );
        """)
    conn.commit()
    yield conn
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TEST_TABLE};")
    conn.commit()
    conn.close()

def test_update_versioned_creates_new_row(setup_test_table):
    conn = setup_test_table

    key_fields = {"key_field": "abc"}
    initial_data = {
        "key_field": "abc",
        "value_field": "original",
    }

    # Insert initial row manually
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {TEST_TABLE} (key_field, value_field)
            VALUES (%s, %s)
        """, (initial_data["key_field"], initial_data["value_field"]))
    conn.commit()

    # Apply versioned update
    update_versioned(conn, TEST_TABLE, key_fields, {"value_field": "updated"})

    # Check results
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {TEST_TABLE} WHERE key_field = %s ORDER BY valid_from", ("abc",))
        rows = cur.fetchall()

    assert len(rows) == 2
    assert rows[0][3] is not None  # valid_to is not NULL for old row
    assert rows[1][2] == "updated"
    assert rows[1][4] is None  # valid_to is NULL for new row
