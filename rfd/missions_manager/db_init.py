from tech_utils.db import get_conn

from tech_utils.logger import init_logger
logger = init_logger("RFD_MM_DBinit")


def db_init():
    with get_conn() as conn:
        logger.info("RFDMM tables start creation")
        try:
            with conn.cursor() as cur:
                cur.execute("""    
                    CREATE TABLE IF NOT EXISTS grfp_missions (
                    id SERIAL PRIMARY KEY,
                    mission_id UUID NOT NULL,
                    mission_group VARCHAR DEFAULT 'default',
                    user_id varchar(255),
                    location varchar(255),
                    time_window varchar(255),
                    drone_type varchar(128),
                    status varchar(32) DEFAULT 'new',
                    parameters JSONB,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                    valid_to TIMESTAMPTZ DEFAULT NULL,
                    UNIQUE (mission_id, valid_from)
                    );
                    CREATE UNIQUE INDEX ON grfp_missions(mission_id) WHERE valid_to IS NULL;
                            
                    CREATE TABLE IF NOT EXISTS grfp_mission_groups (
                    id SERIAL PRIMARY KEY,
                    mission_group VARCHAR NOT NULL,
                    parameters JSONB,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                    valid_to TIMESTAMPTZ DEFAULT NULL,
                    UNIQUE (mission_group, valid_from)
                    );
                    CREATE UNIQUE INDEX ON grfp_mission_groups(mission_group) WHERE valid_to IS NULL;


                    CREATE TABLE IF NOT EXISTS grfp_drone_types (
                            id SERIAL PRIMARY KEY,
                            drone_type_id INT NOT NULL,
                            drone_type_name VARCHAR(128),
                            status VARCHAR(128) DEFAULT 'available',
                            specification JSONB,
                            created_at TIMESTAMPTZ DEFAULT now(),
                            valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                            valid_to TIMESTAMPTZ DEFAULT NULL,
                            UNIQUE (drone_type_id, valid_from)
                            );
                            CREATE UNIQUE INDEX ON grfp_drone_types(drone_type_id) WHERE valid_to IS NULL;
                    
                    CREATE TABLE IF NOT EXISTS grfp_locations (
                            id SERIAL PRIMARY KEY,
                            location_id INT NOT NULL,
                            location_name varchar(64),
                            location_description varchar(255),
                            status varchar(128) DEFAULT 'available',
                            created_at TIMESTAMPTZ DEFAULT now(),
                            valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                            valid_to TIMESTAMPTZ DEFAULT NULL,
                            UNIQUE (location_id, valid_from)
                            );
                            CREATE UNIQUE INDEX ON grfp_locations(location_id) WHERE valid_to IS NULL;
                    """)
                
                cur.execute("SELECT * FROM grfp_mission_groups")
                if not cur.fetchone():
                    cur.execute("INSERT INTO grfp_mission_groups (mission_group) VALUES ('default');")
                conn.commit()
                logger.info("RFDMM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDMM tables: {e}")