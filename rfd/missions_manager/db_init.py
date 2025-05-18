from tech_utils.db import get_conn

from tech_utils.logger import init_logger
logger = init_logger("RFD_MissionsManager")


def db_init():
    with get_conn() as conn:
        logger.info("RFDMM tables start creation")
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS grfp_missions (
                    mission_id UUID PRIMARY KEY,
                    user_id varchar(255),
                    location varchar(255),
                    time_window varchar(255),
                    drone_type varchar(128),
                    status varchar(32) DEFAULT 'new',
                    created_at timestamp DEFAULT now(),
                    updated_at timestamp DEFAULT now()
                    );

                    CREATE TABLE IF NOT EXISTS grfp_drone_types (
                            drone_type_id serial PRIMARY KEY,
                            drone_type_name varchar(128),
                            status varchar(128) DEFAULT 'available',
                            specification JSONB,
                            created_at timestamp DEFAULT now(),
                            updated_at timestamp default now()
                            );
                    
                    CREATE TABLE IF NOT EXISTS grfp_locations (
                            location_id serial PRIMARY KEY,
                            location_name varchar(64),
                            location_description varchar(255),
                            status varchar(128) DEFAULT 'available',
                            created_at timestamp DEFAULT now(),
                            updated_at timestamp default now()
                            );
                    """)
                conn.commit()
                logger.info("RFDMM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDMM tables: {e}")