from tech_utils.db import get_conn

def drone_type_val(value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grfp_drone_types WHERE drone_type = %s AND valid_to IS NULL", (value,))
            row = cur.fetchone()
            if not row:
                return False
            return True

def mission_group_val(value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grfp_mission_groups WHERE mission_group = %s AND valid_to IS NULL", (value,))
            row = cur.fetchone()
            if not row:
                return False
            return True
        
def location_val(value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grfp_locations WHERE location = %s AND valid_to IS NULL", (value,))
            row = cur.fetchone()
            if not row:
                return False
            return True

def mission_type_val(value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grfp_mission_types WHERE mission_type = %s AND valid_to IS NULL", (value,))
            row = cur.fetchone()
            if not row:
                return False
            return True
        
def email_val(value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grfp_users WHERE email = %s AND valid_to IS NULL", (value,))
            row = cur.fetchone()
            if not row:
                return False
            return True