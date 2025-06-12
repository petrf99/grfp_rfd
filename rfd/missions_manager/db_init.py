from tech_utils.db import get_conn
from tech_utils.logger import init_logger

logger = init_logger("RFD_MM_DBinit")

def db_init():
    # Establish a connection to the PostgreSQL database
    with get_conn() as conn:
        logger.info("RFDMM tables start creation")
        try:
            with conn.cursor() as cur:
                # === Missions Table ===
                # Stores individual mission records with versioning
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS grfp_missions (
                        id SERIAL PRIMARY KEY,
                        mission_id UUID NOT NULL,                            -- Mission UUID
                        mission_group VARCHAR DEFAULT 'default',             -- Group name
                        mission_type VARCHAR(255),                           -- Type of the mission
                        user_id VARCHAR(255),                                -- Creator user ID
                        location VARCHAR(255),                               -- Location (free text)
                        time_window VARCHAR(255),                            -- Time range (free text)
                        drone_type VARCHAR(128),                             -- Type of drone
                        status VARCHAR(32) DEFAULT 'new',                    -- Mission status
                        parameters JSONB,                                    -- Additional parameters
                        created_at TIMESTAMPTZ DEFAULT now(),                -- Timestamp of record creation
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),       -- Version start
                        valid_to TIMESTAMPTZ DEFAULT NULL,                   -- Version end (NULL = active)
                        UNIQUE (mission_id, valid_from)
                    );
                    CREATE UNIQUE INDEX ON grfp_missions(mission_id) WHERE valid_to IS NULL;

                    -- === Mission Groups Table ===
                    -- Stores mission group metadata (e.g. for grouping several related missions)
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

                    -- === Drone Types Table ===
                    -- Contains the available drone types with versioned specs
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

                    -- === Locations Table ===
                    -- Lists physical or logical locations where missions can take place
                    CREATE TABLE IF NOT EXISTS grfp_locations (
                        id SERIAL PRIMARY KEY,
                        location_id INT NOT NULL,
                        location_name VARCHAR(64),
                        location_description VARCHAR(255),
                        status VARCHAR(128) DEFAULT 'available',
                        created_at TIMESTAMPTZ DEFAULT now(),
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (location_id, valid_from)
                    );
                    CREATE UNIQUE INDEX ON grfp_locations(location_id) WHERE valid_to IS NULL;
                """)

                # Ensure default mission group exists
                cur.execute("SELECT * FROM grfp_mission_groups")
                if not cur.fetchone():
                    cur.execute("INSERT INTO grfp_mission_groups (mission_group) VALUES ('default');")

                conn.commit()
                logger.info("RFDMM tables created")

        except Exception as e:
            logger.error(f"Error while creating RFDMM tables: {e}")
