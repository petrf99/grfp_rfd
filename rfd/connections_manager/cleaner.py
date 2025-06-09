from tech_utils.logger import init_logger
logger = init_logger("RFD_CM_Cleaner")

from tech_utils.db import get_conn, update_versioned
from rfd.connections_manager.tailscale_manager import remove_from_tailnet


def clean_session(session_id, result):
    """
    Cleans up a session by updating its status and VPN connection in the database,
    and removing the associated device from the Tailnet.
    """
    logger.info(f"Cleaning session {session_id} in DB")
    vpn_hostname = None

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check current session status
                cur.execute("""
                    SELECT status
                    FROM grfp_sessions
                    WHERE session_id = %s
                    AND valid_to IS NULL
                """, (session_id,))
                
                row = cur.fetchone()
                if row:
                    status = row[0]
                else:
                    logger.error(f"Session {session_id} not found")
                    return False

                if status != 'in progress':
                    logger.error(f"Session {session_id} is not in progress")
                    return False

                # Get hostname of the VPN connection associated with the session
                cur.execute(f"""
                    SELECT hostname
                    FROM vpn_connections
                    WHERE parent_id = %s
                    AND valid_to IS NULL      
                """, (session_id,))
                
                row = cur.fetchone()
                if row:
                    vpn_hostname = row[0]
        
        # Update session and VPN connection statuses
        update_versioned(conn, 'grfp_sessions', {'session_id': session_id}, {'status': result})
        update_versioned(conn, 'vpn_connections', {'parent_id': session_id}, {'is_active_flg': False})

        logger.info("DB updates finished. Clearing tailnet")

        # Remove device from the Tailnet if hostname is found
        if vpn_hostname:
            remove_from_tailnet(vpn_hostname)

        logger.info(f"Session {session_id} cleaned. Hostname {vpn_hostname} removed from Tailnet")

        return True
    
    except Exception as e:
        logger.exception(f"clean_session for session {session_id} failed with exception {e}")
        return


def cleaner():
    """
    Periodic background job to clean:
    - Duplicate active sessions (keeping only the latest per mission)
    - Expired VPN connections
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Find sessions that are duplicates (not the latest per mission)
                cur.execute("""
                    WITH sorted_sessions AS (
                        SELECT *,
                               ROW_NUMBER() OVER (
                                   PARTITION BY mission_id
                                   ORDER BY valid_from DESC
                               ) AS row_num
                        FROM grfp_sessions
                        WHERE valid_to IS NULL
                        and status = 'in progress'
                    )
                    SELECT session_id
                    FROM sorted_sessions
                    WHERE row_num > 1
                """)
                sessions1 = cur.fetchall()

                # Combine session IDs to clean
                to_delete = {row[0] for row in sessions1}

                # Clean each session
                logger.info("Start cleaning sessions")
                counter = 0
                if to_delete:
                    for sess in to_delete:
                        counter += clean_session(sess, 'abort')
                    logger.info(f"cleaned {len(to_delete)} sessions\n")
                else:
                    logger.info("No sessions to clean")

                # Find expired VPN connections associated with sessions
                logger.info("Start cleaning VPN connections")
                cur.execute("""
                    SELECT parent_id
                    FROM vpn_connections
                    WHERE valid_to IS NULL
                    AND now() > token_expires_at
                    AND parent_name = 'session_id'
                    AND is_active_flg = TRUE
                """)
                sessions2 = cur.fetchall()

                for row in sessions2:
                    id = row[0]
                    update_versioned(conn, 'vpn_connections', {'parent_id': id}, {'is_active_flg': False})
                logger.info("Cleaning VPN connections finished")
                

    except Exception as e:
        logger.error(f"[!] Error cleaner job: {e}\n")


if __name__ == '__main__':
    cleaner()
