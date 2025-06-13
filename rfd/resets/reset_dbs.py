from tech_utils.db import get_conn

from tech_utils.logger import init_logger
logger = init_logger(name="RFD_DBsReset", component="resets")


def reset_db():
    with get_conn() as conn:
        logger.info("Start dropping tables")
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DROP TABLE IF EXISTS grfp_missions;

                    DROP TABLE IF EXISTS grfp_drone_types;
                    
                    DROP TABLE IF EXISTS grfp_locations;

                    DROP TABLE IF EXISTS grfp_mission_groups;
                            
                    DROP TABLE IF EXISTS grfp_mission_types;

                    DROP TABLE IF EXISTS grfp_sessions;
                            
                    DROP TABLE IF EXISTS vpn_connections;

                    DROP TABLE IF EXISTS grfp_users;
                    """)
                conn.commit()
                logger.info("Tables have been dropped")
        except Exception as e:
            logger.error(f"Error while dropping tables tables: {e}")

if __name__ == "__main__":
    reset_db()