from rfd.flight_sessions_manager.vpn_establisher import get_devices, get_auth_keys, delete_auth_key, delete_device

def reset_tailnet():
    devices = get_devices()
    authkeys = get_auth_keys()
    deleted_dev = 0
    deleted_keys = 0

    for d in devices:
        device_id = d["id"]
        if delete_device(device_id):
            deleted_dev += 1

    for key in authkeys:
        key_id = key.get("id")
        if delete_auth_key(key_id):
            deleted_keys += 1

    if deleted_dev + deleted_keys == 0:
        print(f"Nothing found to delete.")
    else:
        print(f"Reset finished. {deleted_dev} devices and {deleted_keys} authkeys removed from Tailnet")

if __name__ == '__main__':
    reset_tailnet()