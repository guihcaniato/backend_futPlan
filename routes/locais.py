from flask import Blueprint, request, jsonify
from sqlalchemy import text
from db import engine
from auth import token_required

bp = Blueprint('locais', __name__)


@bp.route("/locais", methods=["POST"])
@token_required
def create_local(current_user):
    data = request.get_json()

    if not data or not all(key in data for key in ["nome", "capacidade"]):
        return (
            jsonify({"error": "Os campos 'nome' e 'capacidade' são obrigatórios."}),
            400,
        )

    nome = data["nome"]
    capacidade = data["capacidade"]
    disponivel = data.get("disponivel_para_agendamento", True)

    try:
        with engine.connect() as conn:
            query = text(
                """
                INSERT INTO local (nome, capacidade, disponivel_para_agendamento)
                VALUES (:nome, :capacidade, :disponivel)
            """
            )
            params = {"nome": nome, "capacidade": capacidade, "disponivel": disponivel}

            result = conn.execute(query, params)
            conn.commit()

            novo_local_id = result.lastrowid

        return (
            jsonify(
                {
                    "message": f"Local '{nome}' cadastrado com sucesso!",
                    "id_local": novo_local_id,
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/locais", methods=["GET"])
@token_required
def get_locais(current_user):
    try:
        with engine.connect() as conn:
            query = text(
                "SELECT id_local, nome, capacidade, disponivel_para_agendamento FROM local"
            )
            result = conn.execute(query)

            locais = [dict(row._mapping) for row in result]

        return jsonify(locais)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
