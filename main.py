import sys

from resonance.instance import notify_running_instance
from resonance.paths import prepare_data_dir


if __name__ == "__main__":
    if notify_running_instance():
        # Already running; that copy brings its hub to the front.
        sys.exit(0)
    prepare_data_dir()
    # Imported after the data folder exists: importing the backend creates
    # the Spotify client, which keeps its login token there.
    from resonance.app import create_app

    app = create_app()
    app.run()
