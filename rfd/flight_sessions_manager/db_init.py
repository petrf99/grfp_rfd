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
                    id serial PRIMARY KEY,
                    mission_id UUID,
                    token_hash varchar(255) UNIQUE NOT NULL,
                    session_id uuid,
                    is_active_flg boolean DEFAULT TRUE,
                    tag varchar(64),
                    created_at TIMESTAMPTZ DEFAULT now(),
                    expires_at TIMESTAMPTZ,
                    used_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ DEFAULT now()
                );
                    CREATE TABLE IF NOT EXISTS grfp_sm_sessions (
                        session_id UUID PRIMARY KEY,
                        status varchar(64) default 'new',
                        created_at TIMESTAMPTZ DEFAULT now()  ,
                        updated_at TIMESTAMPTZ default now()
                        );

                    CREATE TABLE IF NOT EXISTS vpn_connections (
                        mission_id uuid PRIMARY KEY,
                        session_id uuid,
                        gcs_ready_flg boolean DEFAULT FALSE,
                        client_ready_flg boolean DEFAULT FALSE,
                        tailscale_name_gcs varchar,
                        tailscale_name_client varchar,
                        gcs_ip varchar,
                        client_ip varchar,
                        status varchar DEFAULT 'waiting',  -- или ready, connected
                        created_at TIMESTAMPTZ DEFAULT now(),
                        updated_at TIMESTAMPTZ default now()
                    );
                    """)
                conn.commit()
                logger.info("RFDSM tables created")
        except Exception as e:
            logger.error(f"Error while creating RFDSM tables: {e}")