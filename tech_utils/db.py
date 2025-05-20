import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


from datetime import datetime, timezone

def update_versioned(
    conn,
    table: str,
    key_field: str,
    key_value,
    update_fields: dict,
):
    """
    Обновляет версионную таблицу:
    - закрывает текущую версию
    - вставляет новую с новыми значениями
    """
    now = datetime.now(timezone.utc)

    # 1. Закрыть текущую активную запись
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {table}
                SET valid_to = %s
                WHERE {key_field} = %s AND valid_to IS NULL
                """,
                (now, key_value),
            )
    except psycopg2.errors.UndefinedTable as e:
        raise RuntimeError(f"Table '{table}' not found: {e}")
    except psycopg2.errors.UndefinedColumn as e:
        return
        #raise RuntimeError(f"Column '{key_field}' not found in table '{table}': {e}")


    # 2. Получить последнюю строку как шаблон
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM {table}
            WHERE {key_field} = %s
            ORDER BY valid_from DESC
            LIMIT 1
            """,
            (key_value,)
        )
        last_row = cur.fetchone()
        desc = [d.name for d in cur.description]

    if not last_row:
        raise ValueError(f"No existing row found for {key_field} = {key_value}")

    # 3. Создать новую запись на основе старой
    new_row = dict(zip(desc, last_row))

    # Обновляем нужные поля
    new_row.update(update_fields)

    # Обновляем системные поля
    new_row["valid_from"] = now
    new_row["valid_to"] = None
    new_row["created_at"] = now

    # Удаляем автоинкрементный id, если есть
    new_row.pop("id", None)

    # Формируем INSERT-запрос
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
