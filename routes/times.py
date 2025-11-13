from flask import Blueprint, request, jsonify
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from db import engine
from auth import token_required
from datetime import datetime, timedelta, timezone

bp = Blueprint('times', __name__)


@bp.route("/times", methods=["POST"])
@token_required
def create_time(current_user):
    data = request.get_json()

    if not data or "nome_time" not in data:
        return jsonify({"error": "O campo 'nome_time' é obrigatório."}), 400

    nome_time = data["nome_time"]
    cor_uniforme = data.get("cor_uniforme")
    id_responsavel = current_user._mapping["id_usuario"]

    try:
        with engine.begin() as conn:  # Use .begin() para transação
            query = text(
                """
                INSERT INTO time (nome_time, fk_responsavel_time, cor_uniforme)
                VALUES (:nome_time, :fk_responsavel_time, :cor_uniforme)
            """
            )

            params = {
                "nome_time": nome_time,
                "fk_responsavel_time": id_responsavel,
                "cor_uniforme": cor_uniforme,
            }

            result = conn.execute(query, params)
            novo_time_id = result.lastrowid

            # Adiciona o capitão como primeiro membro do time
            query_add_captain = text(
                """
                INSERT INTO time_membros (fk_usuario, fk_time)
                VALUES (:fk_usuario, :fk_time)
                """
            )
            conn.execute(query_add_captain, {"fk_usuario": id_responsavel, "fk_time": novo_time_id})

        return (
            jsonify(
                {
                    "message": f"Time '{nome_time}' criado com sucesso!",
                    "id_time": novo_time_id,
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/times", methods=["GET"])
@token_required
def get_times(current_user):
    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT 
                    t.id_time, 
                    t.nome_time, 
                    t.cor_uniforme, 
                    u.nome AS nome_responsavel
                FROM 
                    time AS t
                JOIN 
                    usuario AS u ON t.fk_responsavel_time = u.id_usuario
            """
            )

            result = conn.execute(query)
            times = [dict(row._mapping) for row in result]

        return jsonify(times)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/times/<int:id_time>/membros", methods=["POST"])
@token_required
def add_member(current_user, id_time):
    id_capitao = current_user._mapping["id_usuario"]
    data = request.get_json()

    if not data or "id_usuario" not in data:
        return (
            jsonify({"error": "O campo 'id_usuario' a ser adicionado é obrigatório."}),
            400,
        )

    id_novo_membro = data["id_usuario"]
    numero_camisa = data.get("numero_camisa")

    try:
        with engine.connect() as conn:
            query_check_owner = text(
                "SELECT fk_responsavel_time FROM time WHERE id_time = :id_time"
            )
            time_info = conn.execute(query_check_owner, {"id_time": id_time}).fetchone()

            if not time_info:
                return jsonify({"error": "Time não encontrado."}), 404

            if time_info._mapping["fk_responsavel_time"] != id_capitao:
                return (
                    jsonify(
                        {
                            "error": "Acesso negado. Apenas o capitão pode adicionar membros."
                        }
                    ),
                    403,
                )

            if numero_camisa is not None:
                query_check_number = text(
                    """
                    SELECT 1 FROM time_membros 
                    WHERE fk_time = :fk_time AND numero_camisa = :numero_camisa
                """
                )
                camisa_ja_existe = conn.execute(
                    query_check_number,
                    {"fk_time": id_time, "numero_camisa": numero_camisa},
                ).fetchone()

                if camisa_ja_existe:
                    return (
                        jsonify(
                            {
                                "error": f"A camisa número {numero_camisa} já está em uso neste time."
                            }
                        ),
                        409,
                    )

            query_check_member = text(
                "SELECT 1 FROM time_membros WHERE fk_usuario = :fk_usuario AND fk_time = :fk_time"
            )
            ja_eh_membro = conn.execute(
                query_check_member, {"fk_usuario": id_novo_membro, "fk_time": id_time}
            ).fetchone()

            if ja_eh_membro:
                return jsonify({"error": "Este usuário já é membro do time."}), 409

            query_insert = text(
                """
                INSERT INTO time_membros (fk_usuario, fk_time, numero_camisa)
                VALUES (:fk_usuario, :fk_time, :numero_camisa)
            """
            )
            params = {
                "fk_usuario": id_novo_membro,
                "fk_time": id_time,
                "numero_camisa": numero_camisa,
            }
            conn.execute(query_insert, params)
            conn.commit()

        return jsonify({"message": "Usuário adicionado ao time com sucesso!"}), 201

    except IntegrityError:
        return (
            jsonify(
                {
                    "error": "Não foi possível adicionar o membro. Verifique se o ID do usuário é válido."
                }
            ),
            400,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/times/<int:id_time>/membros", methods=["GET"])
@token_required
def get_members(current_user, id_time):
    try:
        with engine.connect() as conn:
            query_check_time = text("SELECT 1 FROM time WHERE id_time = :id_time")
            time_existe = conn.execute(query_check_time, {"id_time": id_time}).fetchone()

            if not time_existe:
                return jsonify({"error": "Time não encontrado."}), 404

            query = text(
                """
                SELECT 
                    u.id_usuario,
                    u.nome,
                    u.email,
                    tm.numero_camisa
                FROM 
                    time_membros AS tm
                JOIN 
                    usuario AS u ON tm.fk_usuario = u.id_usuario
                WHERE 
                    tm.fk_time = :id_time
            """
            )

            result = conn.execute(query, {"id_time": id_time})

            membros = [dict(row._mapping) for row in result]

        return jsonify(membros)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/times/<int:id_time>/membros/<int:id_usuario_membro>', methods=['DELETE'])
@token_required
def remove_member(current_user, id_time, id_usuario_membro):
    id_capitao = current_user._mapping['id_usuario']

    if id_capitao == id_usuario_membro:
        return jsonify({"error": "O capitão não pode se remover do próprio time."}), 400

    try:
        with engine.begin() as conn:
            query_check_owner = text("SELECT fk_responsavel_time FROM time WHERE id_time = :id_time")
            time_info = conn.execute(query_check_owner, {"id_time": id_time}).fetchone()

            if not time_info:
                return jsonify({"error": "Time não encontrado."}), 404

            if time_info._mapping['fk_responsavel_time'] != id_capitao:
                return jsonify({"error": "Acesso negado. Apenas o capitão pode remover membros."}), 403

            query_delete = text("DELETE FROM time_membros WHERE fk_time = :id_time AND fk_usuario = :id_usuario_membro")
            result = conn.execute(query_delete, {"id_time": id_time, "id_usuario_membro": id_usuario_membro})

            if result.rowcount == 0:
                return jsonify({"error": "Membro não encontrado neste time."}), 404

        return jsonify({"message": "Membro removido do time com sucesso."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/times/<int:id_time>', methods=['DELETE'])
@token_required
def delete_time(current_user, id_time):
    id_capitao = current_user._mapping['id_usuario']

    try:
        with engine.begin() as conn:
            query_check_owner = text("SELECT fk_responsavel_time FROM time WHERE id_time = :id_time")
            time_info = conn.execute(query_check_owner, {"id_time": id_time}).fetchone()

            if not time_info:
                return jsonify({"error": "Time não encontrado."}), 404

            if time_info._mapping['fk_responsavel_time'] != id_capitao:
                return jsonify({"error": "Acesso negado. Apenas o capitão pode excluir o time."}), 403

            query_check_future_games = text(
                """
                SELECT 1 FROM time_partida AS tp
                JOIN partida AS p ON tp.fk_partida = p.id_partida
                JOIN agendamento AS a ON p.fk_agendamento = a.id_agendamento
                WHERE tp.fk_time = :id_time AND a.dthr_ini > :agora
                LIMIT 1
            """
            )

            future_game = conn.execute(query_check_future_games, {"id_time": id_time, "agora": datetime.now(timezone.utc)}).fetchone()

            if future_game:
                return jsonify({"error": "Não é possível excluir o time. Cancele todas as partidas futuras agendadas primeiro."}), 409

            conn.execute(text("DELETE FROM time_membros WHERE fk_time = :id_time"), {"id_time": id_time})
            conn.execute(text("DELETE FROM time WHERE id_time = :id_time"), {"id_time": id_time})

        return jsonify({"message": "Time e todos os seus membros foram removidos com sucesso."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/times/<int:id_time>', methods=['PUT'])
@token_required
def update_time(current_user, id_time):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Nenhum dado enviado para atualização."}), 400

    id_capitao_atual = current_user._mapping['id_usuario']

    try:
        with engine.begin() as conn:
            query_check_owner = text("SELECT fk_responsavel_time FROM time WHERE id_time = :id_time")
            time_info = conn.execute(query_check_owner, {"id_time": id_time}).fetchone()

            if not time_info:
                return jsonify({"error": "Time não encontrado."}), 404

            if time_info._mapping['fk_responsavel_time'] != id_capitao_atual:
                return jsonify({"error": "Acesso negado. Apenas o capitão pode editar o time."}), 403

            novo_capitao_id = data.get('fk_responsavel_time')
            if novo_capitao_id:
                query_check_member = text("SELECT 1 FROM time_membros WHERE fk_time = :id_time AND fk_usuario = :id_usuario")
                novo_capitao_eh_membro = conn.execute(query_check_member, {"id_time": id_time, "id_usuario": novo_capitao_id}).fetchone()

                if not novo_capitao_eh_membro:
                    return jsonify({"error": "O novo capitão deve ser um membro do time."}), 400

            allowed_fields = ['nome_time', 'cor_uniforme', 'fk_responsavel_time']
            update_fields = []
            params = {}

            for field in allowed_fields:
                if field in data:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = data[field]

            if not update_fields:
                return jsonify({"error": "Nenhum campo válido para atualização foi enviado."}), 400

            params['id_time'] = id_time
            query_str = f"UPDATE time SET {', '.join(update_fields)} WHERE id_time = :id_time"
            conn.execute(text(query_str), params)

            return jsonify({"message": "Time atualizado com sucesso."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/times/<int:id_time>/membros/<int:id_usuario_membro>', methods=['PUT'])
@token_required
def update_member_shirt_number(current_user, id_time, id_usuario_membro):
    """Atualiza o número da camisa de um membro do time. Apenas para o capitão."""
    data = request.get_json()
    if not data or 'numero_camisa' not in data:
        return jsonify({"error": "O campo 'numero_camisa' é obrigatório."}), 400

    numero_camisa = data['numero_camisa']
    id_capitao_requisitante = current_user._mapping['id_usuario']

    try:
        with engine.begin() as conn:
            # 1. Verificar se o requisitante é o capitão do time
            query_check_owner = text("SELECT fk_responsavel_time FROM time WHERE id_time = :id_time")
            time_info = conn.execute(query_check_owner, {"id_time": id_time}).fetchone()

            if not time_info:
                return jsonify({"error": "Time não encontrado."}), 404

            if time_info._mapping['fk_responsavel_time'] != id_capitao_requisitante:
                return jsonify({"error": "Acesso negado. Apenas o capitão pode alterar o número da camisa."}), 403

            # 2. Verificar se o usuário a ser atualizado é membro do time
            query_check_member = text("SELECT 1 FROM time_membros WHERE fk_time = :id_time AND fk_usuario = :id_usuario_membro")
            is_member = conn.execute(query_check_member, {"id_time": id_time, "id_usuario_membro": id_usuario_membro}).fetchone()

            if not is_member:
                return jsonify({"error": "Usuário não é membro deste time."}), 404

            # 3. Verificar se o número da camisa já está em uso por OUTRO membro
            query_check_number = text(
                """
                SELECT 1 FROM time_membros 
                WHERE fk_time = :id_time AND numero_camisa = :numero_camisa AND fk_usuario != :id_usuario_membro
                """
            )
            camisa_ja_existe = conn.execute(
                query_check_number,
                {"id_time": id_time, "numero_camisa": numero_camisa, "id_usuario_membro": id_usuario_membro},
            ).fetchone()

            if camisa_ja_existe:
                return jsonify({"error": f"A camisa número {numero_camisa} já está em uso neste time."}), 409

            # 4. Atualizar o número da camisa
            query_update = text(
                "UPDATE time_membros SET numero_camisa = :numero_camisa WHERE fk_time = :id_time AND fk_usuario = :id_usuario_membro"
            )
            conn.execute(query_update, {"numero_camisa": numero_camisa, "id_time": id_time, "id_usuario_membro": id_usuario_membro})

        return jsonify({"message": "Número da camisa atualizado com sucesso."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
