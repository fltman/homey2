from flask import Flask
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For session handling

from app import routes 