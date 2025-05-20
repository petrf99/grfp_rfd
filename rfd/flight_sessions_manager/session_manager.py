from tech_utils.logger import init_logger
logger = init_logger("RFD_SessionManager")

from tech_utils.db import get_conn

from datetime import datetime, timezone

from rfd.flight_sessions_manager.vpn_establisher import clear_tailnet
from rfd.flight_sessions_manager.token_manager import deactivate_token_db


def close_session(mission_id, session_id, result):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM grfp_sm_sessions
                    WHERE session_id = %s
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

                if result == 'finish':
                    # Обновим миссию
                    cur.execute("""
                        UPDATE grfp_missions
                        SET status = 'finish',
                            updated_at = %s
                        WHERE mission_id = %s
                    """, (datetime.now(timezone.utc), mission_id))

                    logger.info(f"Mission {mission_id} finished")
                
                # Write session to db
                cur.execute("""
                    UPDATE grfp_sm_sessions 
                    SET status = %s
                    where session_id = %s
                """, (result, session_id, ))

                cur.execute("""
                    UPDATE vpn_connections
                    SET status = %s
                    where session_id = %s
                """, (result, session_id, ))
                conn.commit()

        deactivate_token_db(session_id)

        clear_tailnet(session_id)

        return
    
    except Exception as e:
        logger.exception(f"GCS-session-finish for session {session_id} failed with exception {e}")
        return