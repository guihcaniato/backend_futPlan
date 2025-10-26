# Minimal Flask entrypoint — registra apenas blueprints e expõe `app`
from flask import Flask, request, jsonify
from flask_cors import CORS


# Import blueprints
from routes.auth import bp as auth_bp
from routes.users import bp as users_bp
from routes.times import bp as times_bp
from routes.locais import bp as locais_bp
from routes.partidas import bp as partidas_bp


app = Flask(__name__)

# Durante desenvolvimento permita a origem do Vite (ex: http://localhost:5173)
CORS(app, resources={r"/*": {"origins": "http://localhost:8080"}}, supports_credentials=True)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(times_bp)
app.register_blueprint(locais_bp)
app.register_blueprint(partidas_bp)


@app.route('/')
def hello_world():
    return '<h1>Backend do FutPlan está no ar!</h1>'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
