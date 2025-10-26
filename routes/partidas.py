from flask import Blueprint, request, jsonify
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from db import engine
from auth import token_required
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError

bp = Blueprint('partidas', __name__)


@bp.route("/partidas", methods=["POST"])
@token_required
def create_partida(current_user):
    data = request.get_json()

    required_fields = [
        "id_time_casa",
        "id_time_visitante",
        "id_local",
        "dthr_ini",
        "dthr_fim",
    ]
    if not data or not all(key in data for key in required_fields):
        return (
            jsonify({
                "error": "Campos obrigatórios: id_time_casa, id_time_visitante, id_local, dthr_ini, dthr_fim."
            }),
            400,
        )

    id_capitao = current_user._mapping["id_usuario"]
    id_time_casa = data["id_time_casa"]
    id_time_visitante = data["id_time_visitante"]
    id_local = data["id_local"]

    try:
        dthr_ini = datetime.fromisoformat(data["dthr_ini"])
        dthr_fim = datetime.fromisoformat(data["dthr_fim"])
    except ValueError:
        return (
            jsonify({"error": "Formato de data inválido. Use AAAA-MM-DD HH:MM:SS."}),
            400,
        )

    if id_time_casa == id_time_visitante:
        return (
            jsonify({"error": "O time da casa e o visitante não podem ser o mesmo."}),
            400,
        )

    if dthr_ini >= dthr_fim:
        return (
            jsonify({"error": "A data/hora de início deve ser anterior à de término."}),
            400,
        )

    try:
        with engine.begin() as conn:
            query_get_data = text(
                """
                SELECT t.fk_responsavel_time, l.horario_abertura, l.horario_fechamento 
                FROM time AS t, local AS l
                WHERE t.id_time = :id_time AND l.id_local = :id_local
            """
            )
            result = conn.execute(
                query_get_data, {"id_time": id_time_casa, "id_local": id_local}
            ).fetchone()

            if not result:
                return jsonify({"error": "Time da casa ou Local não encontrado."}), 404

            dados = result._mapping
            if dados["fk_responsavel_time"] != id_capitao:
                return (
                    jsonify({
                        "error": "Acesso negado. Apenas o capitão do time da casa pode agendar partidas."
                    }),
                    403,
                )

            horario_abertura_do_dia = dados["horario_abertura"]
            horario_fechamento_do_dia = dados["horario_fechamento"]
            local_fechado_o_dia_todo = False
            motivo_fechamento = ""

            query_check_exception = text(
                """
                SELECT motivo, horario_abertura_excecao, horario_fechamento_excecao
                FROM local_excecoes 
                WHERE fk_local = :id_local AND data_excecao = DATE(:dthr_ini)
            """
            )
            excecao = conn.execute(
                query_check_exception, {"id_local": id_local, "dthr_ini": dthr_ini}
            ).fetchone()

            if excecao:
                ex_data = excecao._mapping
                if ex_data["horario_abertura_excecao"] is None:
                    local_fechado_o_dia_todo = True
                    motivo_fechamento = (
                        ex_data["motivo"] or "fechado por motivo não especificado"
                    )
                else:
                    horario_abertura_do_dia = ex_data["horario_abertura_excecao"]
                    horario_fechamento_do_dia = ex_data["horario_fechamento_excecao"]

            if local_fechado_o_dia_todo:
                return (
                    jsonify({
                        "error": f"Não é possível agendar neste dia. O local estará fechado.",
                        "motivo": motivo_fechamento,
                    }),
                    409,
                )

            if horario_abertura_do_dia and horario_fechamento_do_dia:
                hora_inicio_partida = dthr_ini.time()
                hora_fim_partida = dthr_fim.time()
                timedelta_inicio = timedelta(
                    hours=hora_inicio_partida.hour, minutes=hora_inicio_partida.minute
                )
                timedelta_fim = timedelta(
                    hours=hora_fim_partida.hour, minutes=hora_fim_partida.minute
                )

                if not (
                    horario_abertura_do_dia <= timedelta_inicio
                    and timedelta_fim <= horario_fechamento_do_dia
                ):
                    return (
                        jsonify({
                            "error": "O horário solicitado está fora do horário de funcionamento para este dia.",
                            "funcionamento_do_dia": f"Das {horario_abertura_do_dia} às {horario_fechamento_do_dia}",
                        }),
                        409,
                    )

            query_check_conflict = text(
                """
                SELECT 1 FROM agendamento 
                WHERE fk_local = :id_local AND dthr_ini < :dthr_fim AND dthr_fim > :dthr_ini
            """
            )
            conflito = conn.execute(
                query_check_conflict,
                {"id_local": id_local, "dthr_ini": dthr_ini, "dthr_fim": dthr_fim},
            ).fetchone()

            if conflito:
                return (
                    jsonify({
                        "error": "Horário indisponível. Já existe um agendamento neste local e período."
                    }),
                    409,
                )

            query_insert_agendamento = text(
                "INSERT INTO agendamento (dthr_ini, dthr_fim, fk_local) VALUES (:dthr_ini, :dthr_fim, :fk_local)"
            )
            result_agendamento = conn.execute(
                query_insert_agendamento,
                {"dthr_ini": dthr_ini, "dthr_fim": dthr_fim, "fk_local": id_local},
            )
            id_agendamento = result_agendamento.lastrowid

            query_insert_partida = text(
                "INSERT INTO partida (fk_responsavel_partida, fk_agendamento) VALUES (:id_capitao, :id_agendamento)"
            )
            result_partida = conn.execute(
                query_insert_partida,
                {"id_capitao": id_capitao, "id_agendamento": id_agendamento},
            )
            id_partida = result_partida.lastrowid

            query_insert_times = text(
                "INSERT INTO time_partida (fk_time, fk_partida, casa_visitante) VALUES (:fk_time, :fk_partida, :cv)"
            )
            conn.execute(
                query_insert_times,
                {"fk_time": id_time_casa, "fk_partida": id_partida, "cv": "C"},
            )
            conn.execute(
                query_insert_times,
                {"fk_time": id_time_visitante, "fk_partida": id_partida, "cv": "V"},
            )

        return (
            jsonify({"message": "Partida agendada com sucesso!", "id_partida": id_partida}),
            201,
        )

    except Exception as e:
        return jsonify({"error": "Ocorreu um erro interno.", "details": str(e)}), 500


@bp.route('/partidas', methods=['GET'])
@token_required
def get_partidas(current_user):
    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT 
                    p.id_partida,
                    a.dthr_ini,
                    a.dthr_fim,
                    l.nome AS nome_local,
                    u.nome AS nome_responsavel,
                    (SELECT t.nome_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'C') AS time_casa,
                    (SELECT t.nome_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'V') AS time_visitante
                FROM partida AS p
                JOIN agendamento AS a ON p.fk_agendamento = a.id_agendamento
                JOIN local AS l ON a.fk_local = l.id_local
                JOIN usuario AS u ON p.fk_responsavel_partida = u.id_usuario
                ORDER BY a.dthr_ini ASC
            """
            )

            result = conn.execute(query)
            partidas = [
                {
                    **row._mapping,
                    'dthr_ini': row._mapping['dthr_ini'].isoformat(),
                    'dthr_fim': row._mapping['dthr_fim'].isoformat(),
                }
                for row in result
            ]

        return jsonify(partidas)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/partidas/<int:id_partida>', methods=['GET'])
@token_required
def get_partida_details(current_user, id_partida):
    try:
        with engine.connect() as conn:
            query_partida = text(
                """
                SELECT 
                    p.id_partida, a.dthr_ini, a.dthr_fim, l.nome AS nome_local, u.nome AS nome_responsavel,
                    (SELECT t.id_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'C') AS id_time_casa,
                    (SELECT t.nome_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'C') AS nome_time_casa,
                    (SELECT t.id_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'V') AS id_time_visitante,
                    (SELECT t.nome_time FROM time_partida tp JOIN time t ON tp.fk_time = t.id_time WHERE tp.fk_partida = p.id_partida AND tp.casa_visitante = 'V') AS nome_time_visitante
                FROM partida AS p
                JOIN agendamento AS a ON p.fk_agendamento = a.id_agendamento
                JOIN local AS l ON a.fk_local = l.id_local
                JOIN usuario AS u ON p.fk_responsavel_partida = u.id_usuario
                WHERE p.id_partida = :id_partida
            """
            )

            result_partida = conn.execute(query_partida, {"id_partida": id_partida}).fetchone()

            if not result_partida:
                return jsonify({"error": "Partida não encontrada."}), 404

            partida_details = dict(result_partida._mapping)
            partida_details['dthr_ini'] = partida_details['dthr_ini'].isoformat()
            partida_details['dthr_fim'] = partida_details['dthr_fim'].isoformat()

        return jsonify(partida_details)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/partidas/<int:id_partida>/presenca', methods=['POST'])
@token_required
def confirm_presence(current_user, id_partida):
    data = request.get_json()
    status = data.get('status')
    valid_statuses = ['Confirmado', 'Duvida', 'Recusado']
    if not status or status not in valid_statuses:
        return jsonify({'error': f"O campo 'status' é obrigatório e deve ser um de: {valid_statuses}"}), 400

    id_usuario = current_user._mapping['id_usuario']

    try:
        with engine.begin() as conn:
            query_check_player = text(
                """
                SELECT 1 FROM time_membros tm
                JOIN time_partida tp ON tm.fk_time = tp.fk_time
                WHERE tm.fk_usuario = :id_usuario AND tp.fk_partida = :id_partida
            """
            )
            is_player_in_match = conn.execute(query_check_player, {"id_usuario": id_usuario, "id_partida": id_partida}).fetchone()

            if not is_player_in_match:
                return jsonify({'error': 'Acesso negado. Você não é membro de nenhum dos times desta partida.'}), 403

            query_upsert = text(
                """
                INSERT INTO partida_presenca (fk_partida, fk_usuario, status)
                VALUES (:id_partida, :id_usuario, :status)
                ON DUPLICATE KEY UPDATE status = :status
            """
            )
            conn.execute(query_upsert, {"id_partida": id_partida, "id_usuario": id_usuario, 'status': status})

        return jsonify({'message': f"Sua presença foi atualizada para '{status}'."}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/partidas/<int:id_partida>/presenca', methods=['GET'])
@token_required
def get_presence_list(current_user, id_partida):
    try:
        with engine.connect() as conn:
            query_check_match = text("SELECT 1 FROM partida WHERE id_partida = :id_partida")
            match_exists = conn.execute(query_check_match, {'id_partida': id_partida}).fetchone()

            if not match_exists:
                return jsonify({'error': 'Partida não encontrada.'}), 404

            query_get_list = text(
                """
                SELECT 
                    u.id_usuario,
                    u.nome AS nome_jogador,
                    pp.status,
                    t.nome_time
                FROM partida_presenca AS pp
                JOIN usuario AS u ON pp.fk_usuario = u.id_usuario
                JOIN time_partida AS tp ON pp.fk_partida = tp.fk_partida
                JOIN time_membros AS tm ON u.id_usuario = tm.fk_usuario AND tp.fk_time = tm.fk_time
                JOIN time AS t ON tm.fk_time = t.id_time
                WHERE pp.fk_partida = :id_partida
                ORDER BY t.nome_time, u.nome;
            """
            )

            result = conn.execute(query_get_list, {'id_partida': id_partida})
            presence_list = [dict(row._mapping) for row in result]

        return jsonify(presence_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/partidas/<int:id_partida>', methods=['DELETE'])
@token_required
def cancel_partida(current_user, id_partida):
    id_usuario_logado = current_user._mapping['id_usuario']

    try:
        with engine.begin() as conn:
            query_get_partida = text("SELECT fk_responsavel_partida, fk_agendamento FROM partida WHERE id_partida = :id_partida")
            partida_info = conn.execute(query_get_partida, {'id_partida': id_partida}).fetchone()

            if not partida_info:
                return jsonify({'error': 'Partida não encontrada.'}), 404

            if partida_info._mapping['fk_responsavel_partida'] != id_usuario_logado:
                return jsonify({'error': 'Acesso negado. Apenas quem agendou a partida pode cancelá-la.'}), 403

            conn.execute(text('DELETE FROM time_partida WHERE fk_partida = :id_partida'), {'id_partida': id_partida})
            conn.execute(text('DELETE FROM partida_presenca WHERE fk_partida = :id_partida'), {'id_partida': id_partida})
            conn.execute(text('DELETE FROM partida WHERE id_partida = :id_partida'), {'id_partida': id_partida})

            id_agendamento = partida_info._mapping['fk_agendamento']
            conn.execute(text('DELETE FROM agendamento WHERE id_agendamento = :id_agendamento'), {'id_agendamento': id_agendamento})

        return jsonify({'message': 'Partida cancelada com sucesso e horário liberado.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500