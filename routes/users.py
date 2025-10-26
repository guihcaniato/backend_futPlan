from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from db import get_connection, engine
from sqlalchemy import text
from auth import token_required

bp = Blueprint('users', __name__)


@bp.route('/usuarios', methods=['POST'])
def create_usuario():
    data = request.get_json()
    if not data or not all(key in data for key in ['nome', 'email', 'senha']):
        return jsonify({'error': "Dados incompletos. 'nome', 'email' e 'senha' são obrigatórios."}), 400

    nome = data['nome']
    email = data['email']
    senha = data['senha']
    genero = data.get('genero')
    dt_nascimento = data.get('dt_nascimento')
    no_telefone = data.get('no_telefone')

    hashed_password = generate_password_hash(senha)

    try:
        with get_connection() as conn:
            query = text(
                """
                INSERT INTO usuario (nome, email, hash_senha, genero, dt_nascimento, no_telefone)
                VALUES (:nome, :email, :hash_senha, :genero, :dt_nascimento, :no_telefone)
            """
            )
            params = {
                'nome': nome,
                'email': email,
                'hash_senha': hashed_password,
                'genero': genero,
                'dt_nascimento': dt_nascimento,
                'no_telefone': no_telefone,
            }
            conn.execute(query, params)
            conn.commit()

        return jsonify({'message': f"Usuário '{nome}' criado com sucesso!"}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/profile')
@token_required
def get_profile(current_user):
    user_data = {
        'id_usuario': current_user._mapping['id_usuario'],
        'nome': current_user._mapping['nome'],
        'email': current_user._mapping['email'],
        'genero': current_user._mapping['genero'],
        'dt_nascimento': str(current_user._mapping['dt_nascimento']) if current_user._mapping['dt_nascimento'] else None,
        'no_telefone': current_user._mapping['no_telefone']
    }
    return jsonify(user_data)


@bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()

    if not data:
        return jsonify({"error": "Nenhum dado enviado para atualização."}), 400

    id_usuario_logado = current_user._mapping['id_usuario']
    email_atual = current_user._mapping['email']

    novo_email = data.get('email')
    if novo_email and novo_email != email_atual:
        try:
            with engine.connect() as conn:
                query_check_email = text("SELECT id_usuario FROM usuario WHERE email = :email AND id_usuario != :id_logado")
                email_existente = conn.execute(query_check_email, {"email": novo_email, "id_logado": id_usuario_logado}).fetchone()

                if email_existente:
                    return jsonify({"error": "Este e-mail já está em uso por outra conta."}), 409
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    allowed_fields = ['nome', 'email', 'genero', 'dt_nascimento', 'no_telefone']
    update_fields = []
    params = {}

    for field in allowed_fields:
        if field in data:
            update_fields.append(f"{field} = :{field}")
            params[field] = data[field]

    if not update_fields:
        return jsonify({"error": "Nenhum campo válido para atualização foi enviado."}), 400

    params['id_usuario'] = id_usuario_logado

    try:
        with engine.begin() as conn:
            query_str = f"UPDATE usuario SET {', '.join(update_fields)} WHERE id_usuario = :id_usuario"
            conn.execute(text(query_str), params)

            query_get_updated = text("SELECT id_usuario, nome, email, genero, dt_nascimento, no_telefone FROM usuario WHERE id_usuario = :id_usuario")
            updated_user = conn.execute(query_get_updated, {"id_usuario": id_usuario_logado}).fetchone()

            user_data = dict(updated_user._mapping)
            if user_data.get('dt_nascimento'):
                user_data['dt_nascimento'] = str(user_data['dt_nascimento'])

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
