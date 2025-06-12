# main.py
import threading
from rfd.missions_manager.app import main as mission_app
from rfd.connections_manager.app import main as connections_app
from rfd.auth.app import main as auth_app

# Run missions manager
def run_mission():
    mission_app()

# Run connections gcs-client manager
def run_connections():
    connections_app()

# Run authentification service
def run_auth():
    auth_app()

if __name__ == "__main__":

    t1 = threading.Thread(target=run_mission)
    t2 = threading.Thread(target=run_connections) 
    t3 = threading.Thread(target=run_auth)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()
