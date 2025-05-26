from tech_utils.db import get_conn

from tech_utils.logger import init_logger
logger = init_logger("RFD_CM")

def db_init():
    with get_conn() as conn:
        logger.info("RFDCM tables start creation")
        try:
            with conn.cursor() as cur:
                cur.execute("""

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_auth_token ON grfp_auth_tokens(token_hash)
                    WHERE valid_to IS NULL;

                    CREATE TABLE IF NOT EXISTS grfp_sessions (
                        id SERIAL PRIMARY KEY,
                        session_id UUID NOT NULL,
                        mission_id UUID NOT NULL,
                        status VARCHAR(64) DEFAULT 'in progress',
                        created_at TIMESTAMPTZ DEFAULT now(),
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (session_id, valid_from)
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_session_id ON grfp_sessions(session_id)
                    WHERE valid_to IS NULL;

                    CREATE TABLE IF NOT EXISTS vpn_connections (
                        id SERIAL PRIMARY KEY,
                        tag VARCHAR,
                        parent_id VARCHAR NOT NULL,
                        parent_name VARCHAR NOT NULL,
                        hostname VARCHAR NOT NULL,
                        token_hash VARCHAR NOT NULL,
                        token_expires_at TIMESTAMPZ NOT NULL,
                        is_active_flg BOOLEAN NOT NULL DEFAULT true,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (session_id, valid_from)
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_vpn_mission ON vpn_connections(session_id)
                    WHERE valid_to IS NULL;

                    """)
                conn.commit()
                logger.info("RFDCM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDCM tables: {e}")