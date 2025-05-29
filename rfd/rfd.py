# main.py
import threading
from rfd.missions_manager.app import main as mission_app
from rfd.connections_manager.app import main as connections_app

# Run missions manager
def run_mission():
    mission_app()

# Run connections gcs-client manager
def run_connections():
    connections_app()

if __name__ == "__main__":

    t1 = threading.Thread(target=run_mission)
    t2 = threading.Thread(target=run_connections) 

    t1.start()
    t2.start()

    t1.join()
    t2.join()
