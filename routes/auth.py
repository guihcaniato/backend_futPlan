from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash
from auth import generate_token
from db import get_connection
from sqlalchemy import text

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'senha')):
        return jsonify({'error': "'email' e 'senha' são obrigatórios."}), 400

    email = data['email']
    senha = data['senha']

    try:
        with get_connection() as conn:
            query = text('SELECT id_usuario, nome, hash_senha FROM usuario WHERE email = :email')
            result = conn.execute(query, {'email': email}).fetchone()

        if not result or not check_password_hash(result._mapping['hash_senha'], senha):
            return jsonify({'error': 'Credenciais inválidas.'}), 401

        token = generate_token(result._mapping['id_usuario'], result._mapping['nome'])
        return jsonify({'access_token': token})
    except Exception as e:
        current_app.logger.error(f'Erro no login: {e}')
        return jsonify({'error': str(e)}), 500
