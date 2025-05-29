from tech_utils.db import get_conn
from tech_utils.logger import init_logger
logger = init_logger("RFD_CM")

def db_init():
    with get_conn() as conn:
        logger.info("RFDCM tables start creation")
        try:
            with conn.cursor() as cur:
                # Create the grfp_sessions table to track flight sessions
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS grfp_sessions (
                        id SERIAL PRIMARY KEY,                                -- Internal row ID
                        session_id UUID NOT NULL,                             -- Public unique session identifier
                        mission_id UUID NOT NULL,                             -- Associated mission ID
                        status VARCHAR(64) DEFAULT 'in progress',             -- Session status: in progress, finished, aborted, etc.
                        created_at TIMESTAMPTZ DEFAULT now(),                 -- Creation timestamp
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),        -- Versioning start timestamp
                        valid_to TIMESTAMPTZ DEFAULT NULL,                    -- Versioning end timestamp (null = current version)
                        UNIQUE (session_id, valid_from)                       -- Ensure unique version per session
                    );

                    -- Unique index to enforce only one active version per session
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_session_id ON grfp_sessions(session_id)
                    WHERE valid_to IS NULL;

                    -- Create the vpn_connections table to track issued VPN credentials
                    CREATE TABLE IF NOT EXISTS vpn_connections (
                        id SERIAL PRIMARY KEY,                                -- Internal row ID
                        tag VARCHAR,                                          -- Role: "client" or "gcs"
                        parent_id VARCHAR NOT NULL,                           -- Related mission_id or session_id
                        parent_name VARCHAR NOT NULL,                         -- Field name of parent_id ("mission_id" or "session_id")
                        hostname VARCHAR NOT NULL,                            -- Tailscale hostname
                        token_hash VARCHAR NOT NULL,                          -- Hashed version of the issued token
                        token_expires_at TIMESTAMPTZ NOT NULL,                -- Token expiration timestamp
                        is_active_flg BOOLEAN NOT NULL DEFAULT true,          -- Logical deletion flag (false = inactive)
                        created_at TIMESTAMPTZ DEFAULT now(),                 -- Creation timestamp
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),        -- Versioning start timestamp
                        valid_to TIMESTAMPTZ DEFAULT NULL,                    -- Versioning end timestamp (null = current version)
                        UNIQUE (id, valid_from)                               -- Ensure version uniqueness per record
                    );

                    -- Unique index to enforce only one active version per VPN connection
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_vpn_mission ON vpn_connections(id)
                    WHERE valid_to IS NULL;
                """)
                conn.commit()
                logger.info("RFDCM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDCM tables: {e}")
