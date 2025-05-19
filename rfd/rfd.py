# main.py
import threading
from rfd.missions_manager.app import main as mission_app
from rfd.flight_sessions_manager.app import main as session_app


def run_mission():
    mission_app()

def run_session():
    session_app()

if __name__ == "__main__":

    t1 = threading.Thread(target=run_mission)
    t2 = threading.Thread(target=run_session)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
