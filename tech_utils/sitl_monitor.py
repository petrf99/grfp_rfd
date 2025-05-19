from pymavlink import mavutil

conn = mavutil.mavlink_connection('udp:127.0.0.1:14550')
conn.wait_heartbeat()
print(f"✅ Connected: system={conn.target_system}, component={conn.target_component}")

# Запрос потока данных от автопилота
conn.mav.request_data_stream_send(
    conn.target_system,
    conn.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL,
    2,   # 2 Гц (можно больше)
    1    # Включить
)

while True:
    msg = conn.recv_match(blocking=True)
    if not msg:
        continue

    mtype = msg.get_type()

    if mtype == "HEARTBEAT":
        mode = mavutil.mode_string_v10(msg)
        armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
        print(f"[HEARTBEAT] Mode: {mode}, Armed: {armed}")

    elif mtype == "RC_CHANNELS_RAW":
        channels = [getattr(msg, f'chan{i}_raw', 0) for i in range(1, 9)]
        print(f"[RC] {channels}")

    elif mtype == "GLOBAL_POSITION_INT":
        print(f"[POS] lat={msg.lat/1e7:.6f}, lon={msg.lon/1e7:.6f}, alt={msg.alt/1000}m")

    elif mtype == "ATTITUDE":
        print(f"[ATT] pitch={msg.pitch:.2f}, roll={msg.roll:.2f}, yaw={msg.yaw:.2f}")

    elif mtype == "STATUSTEXT":
        print(f"[STATUSTEXT] {msg.severity} - {msg.text}")
