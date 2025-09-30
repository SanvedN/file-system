import subprocess
import sys
import signal

# Define your services here
# Replace these paths and modules with your actual ones
services = {
    "main": {
        "app_module": "app:app",  # e.g. app.py contains FastAPI instance named "app"
        "app_dir": "./",  # path to the folder containing app.py
        "port": 8000,
    },
    "file_service": {
        "app_module": "app:app",
        "app_dir": "./src/file_service",
        "port": 8001,
    },
    "extraction_service": {
        "app_module": "app:app",
        "app_dir": "./src/extraction_service",
        "port": 8002,
    },
}

processes = []


def start_services():
    for name, svc in services.items():
        print(f"Starting {name} on port {svc['port']}...")
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            svc["app_module"],
            "--host",
            "0.0.0.0",
            "--port",
            str(svc["port"]),
            "--app-dir",
            svc["app_dir"],
        ]
        p = subprocess.Popen(cmd)
        processes.append(p)


def stop_services(signum, frame):
    print("\nStopping all services...")
    for p in processes:
        p.terminate()
    sys.exit(0)


if __name__ == "__main__":
    # Catch SIGINT (Ctrl+C) to gracefully terminate all subprocesses
    signal.signal(signal.SIGINT, stop_services)

    start_services()
    print("All services started. Press Ctrl+C to stop.")

    # Wait indefinitely for processes
    for p in processes:
        p.wait()
