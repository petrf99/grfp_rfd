from tech_utils.db import get_conn

from tech_utils.logger import init_logger
logger = init_logger("RFD_FlightSessionsManager")

def db_init():
    with get_conn() as conn:
        logger.info("RFDSM tables start creation")
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS grfp_sm_auth_tokens (
                        id SERIAL PRIMARY KEY,
                        mission_id UUID,
                        token_hash VARCHAR(255) NOT NULL,
                        session_id UUID,
                        is_active_flg BOOLEAN DEFAULT TRUE,
                        tag VARCHAR(64),
                        created_at TIMESTAMPTZ DEFAULT now(),
                        expires_at TIMESTAMPTZ,
                        used_at TIMESTAMPTZ,
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (token_hash, valid_from)
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_auth_token ON grfp_sm_auth_tokens(token_hash)
                    WHERE valid_to IS NULL;

                    CREATE TABLE IF NOT EXISTS grfp_sm_sessions (
                        id SERIAL PRIMARY KEY,
                        session_id UUID NOT NULL,
                        mission_id UUID NOT NULL,
                        status VARCHAR(64) DEFAULT 'in progress',
                        created_at TIMESTAMPTZ DEFAULT now(),
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (session_id, valid_from)
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_session_id ON grfp_sm_sessions(session_id)
                    WHERE valid_to IS NULL;

                    CREATE TABLE IF NOT EXISTS vpn_connections (
                        id SERIAL PRIMARY KEY,
                        mission_id UUID NOT NULL,
                        session_id UUID NOT NULL,
                        gcs_ready_flg BOOLEAN DEFAULT FALSE,
                        client_ready_flg BOOLEAN DEFAULT FALSE,
                        tailscale_name_gcs VARCHAR,
                        tailscale_name_client VARCHAR,
                        gcs_ip VARCHAR,
                        client_ip VARCHAR,
                        status VARCHAR DEFAULT 'in progress',  -- варианты: abort, in progress, finish
                        created_at TIMESTAMPTZ DEFAULT now(),
                        valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                        valid_to TIMESTAMPTZ DEFAULT NULL,
                        UNIQUE (session_id, valid_from)
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS uq_active_vpn_mission ON vpn_connections(session_id)
                    WHERE valid_to IS NULL;

                    """)
                conn.commit()
                logger.info("RFDSM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDSM tables: {e}")