import sys

from resonance.instance import notify_running_instance
from resonance.setup import setup_spotify


if __name__ == "__main__":
    if notify_running_instance():
        # Already running; that copy brings its hub to the front.
        sys.exit(0)
    if setup_spotify():
        from resonance.app import create_app

        app = create_app()
        app.run()
