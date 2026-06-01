"""WSGI entrypoint for production (gunicorn).

    gunicorn --bind 0.0.0.0:8000 wsgi:application

Kept separate from app.py so the dev server (`python app.py`) and the prod
server reference the same Flask object without app.py's __main__ block running.
"""

from app import app as application

if __name__ == "__main__":
    application.run()
