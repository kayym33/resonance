from resonance.setup import setup_spotify


if __name__ == "__main__":
    if setup_spotify():
        from resonance.frontend import create_app

        app = create_app()
        app.run()
