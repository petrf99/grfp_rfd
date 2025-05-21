from tech_utils.logger import init_logger
logger = init_logger("RFD_SessionManager")

from tech_utils.db import get_conn, update_versioned

from datetime import datetime, timezone

from rfd.flight_sessions_manager.vpn_establisher import clear_tailnet
from rfd.flight_sessions_manager.token_manager import deactivate_token_db


def close_session(session_id, result):
    logger.info(f"Closing session {session_id}")
    conn = get_conn()
    try:
        with conn as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM grfp_sm_sessions
                    WHERE session_id = %s
                    AND valid_to IS NULL
                            """, (session_id,))
                
                row = cur.fetchone()
                if row:
                    status = row[0]
                else:
                    logger.error(f"Session {session_id} not found")
                    return

                if status != 'in progress':
                    logger.error(f"Session {session_id} is not in progress")
                    return

                
        # Update session status
        update_versioned(conn, 'grfp_sm_sessions', {'session_id': session_id}, {'status': result})

        # Upd vpn connection status
        update_versioned(conn, 'vpn_connections', {'session_id': session_id}, {'status':result})

        deactivate_token_db(session_id)

        # Deactivate and delete devices and keys on teilnet
        logger.info("DB updates finished. Clearing tailnet")
        clear_tailnet(session_id)

        logger.info(f"Session {session_id} closed")

        return
    
    except Exception as e:
        logger.exception(f"GCS-session-finish for session {session_id} failed with exception {e}")
        return
    finally:
        conn.close()


def clean_sm_db():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH sorted_sessions AS (
                        SELECT *,
                               ROW_NUMBER() OVER (
                                   PARTITION BY mission_id
                                   ORDER BY valid_from DESC
                               ) AS row_num
                        FROM grfp_sm_sessions
                        WHERE valid_to IS NULL
                        and status = 'in progress'
                    )
                    SELECT session_id
                    FROM sorted_sessions
                    WHERE row_num > 1
                """)
                
                rows = cur.fetchall()

                if rows:
                    for row in rows:
                        session_id = row
                        close_session(session_id, 'abort')
                    logger.info(f"Clean_sm_db: cleaned {len(rows)} sessions\n")
                else:
                    logger.info("Clean_sm_db: No sessions to clean")

                cur.execute("""
                    WITH sorted_tokens AS (
                        SELECT *,
                               ROW_NUMBER() OVER (
                                   PARTITION BY mission_id, tag
                                   ORDER BY valid_from DESC
                               ) AS row_num
                        FROM grfp_sm_auth_tokens
                        WHERE valid_to IS NULL
                        and is_active_flg = TRUE
                    )
                    SELECT session_id, tag
                    FROM sorted_tokens
                    WHERE row_num > 1
                """)

                rows = cur.fetchall()

                if rows:
                    for row in rows:
                        session_id = row[0]
                        deactivate_token_db(session_id, [row[1]])
                    logger.info(f"Clean_sm_db: cleaned {len(rows)} sessions\n")
                else:
                    logger.info("Clean_sm_db: Nothing to clean")

    except Exception as e:
        logger.error(f"[!] Error in clean_sm_db job: {e}\n")


if __name__ == '__main__':
    clean_sm_db()