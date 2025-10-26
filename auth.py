from functools import wraps
from flask import request, jsonify
import jwt
from datetime import datetime, timedelta, timezone
from db import get_connection
from sqlalchemy import text
from config import JWT_SECRET_KEY


def generate_token(user_id: int, name: str, hours_valid: int = 8) -> str:
    payload = {
        'sub': str(user_id),
        'name': name,
        'exp': datetime.now(timezone.utc) + timedelta(hours=hours_valid)
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])


def token_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'message': 'Token está faltando!'}), 401

        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
        else:
            return jsonify({'message': 'Cabeçalho Authorization malformado.'}), 401

        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expirou!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token é inválido!'}), 401
        except Exception as e:
            return jsonify({'error': str(e)}), 500

        # 'sub' was stored as string
        try:
            id_usuario = int(payload.get('sub'))
        except (TypeError, ValueError):
            return jsonify({'message': 'Token é inválido (sub malformado).'}), 401

        # Busca o usuário no banco
        with get_connection() as conn:
            query = text("SELECT * FROM usuario WHERE id_usuario = :id_usuario")
            current_user = conn.execute(query, {'id_usuario': id_usuario}).fetchone()

        if not current_user:
            return jsonify({'message': 'Usuário do token não encontrado.'}), 401

        return func(current_user, *args, **kwargs)

    return wrapper
