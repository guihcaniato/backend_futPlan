import pytest
from app import app as flask_app
from werkzeug.security import generate_password_hash
from contextlib import contextmanager


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client


def make_fake_get_connection():
    """Retorna um context manager que simula conexões/consultas ao banco.

    Ele responde para duas queries esperadas no fluxo de teste:
    - login: SELECT id_usuario, nome, hash_senha FROM usuario WHERE email = :email
    - token lookup: SELECT * FROM usuario WHERE id_usuario = :id_usuario
    """

    class FakeRow:
        def __init__(self, mapping):
            self._mapping = mapping

    class FakeResult:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

        def __iter__(self):
            if self._row is None:
                return iter([])
            return iter([self._row])

    class FakeConn:
        def execute(self, query, params=None):
            q = str(query).lower()
            # Simula a query do endpoint /login
            if 'select id_usuario, nome, hash_senha' in q or 'hash_senha' in q:
                hashed = generate_password_hash('Test1234!')
                row = FakeRow({'id_usuario': 1, 'nome': 'test_user', 'hash_senha': hashed})
                return FakeResult(row)

            # Simula a query do decorador token_required (/profile)
            if 'select * from usuario where id_usuario' in q:
                row = FakeRow({
                    'id_usuario': 1,
                    'nome': 'test_user',
                    'email': 'test_user@example.com',
                    'genero': None,
                    'dt_nascimento': None,
                    'no_telefone': None
                })
                return FakeResult(row)

            return FakeResult(None)

        def close(self):
            pass

    @contextmanager
    def ctx():
        conn = FakeConn()
        yield conn

    return ctx


def test_login_and_profile_flow_monkeypatched_db(client, monkeypatch):
    """Teste do fluxo /login -> /profile sem depender de um MySQL real.

    Substituímos `get_connection()` por um context manager fake que retorna
    resultados esperados para as queries usadas pelos endpoints.
    """
    from db import get_connection as real_get_connection

    fake_ctx = make_fake_get_connection()
    # Patching the actual symbols imported by the route modules and auth decorator
    monkeypatch.setattr('db.get_connection', fake_ctx)
    monkeypatch.setattr('routes.auth.get_connection', fake_ctx)
    monkeypatch.setattr('routes.users.get_connection', fake_ctx)
    monkeypatch.setattr('auth.get_connection', fake_ctx)

    login_payload = {"email": "test_user@example.com", "senha": "Test1234!"}

    # 1) Login
    rv = client.post('/login', json=login_payload)
    assert rv.status_code == 200, f"Login falhou: {rv.data}"
    data = rv.get_json()
    assert 'access_token' in data
    token = data['access_token']

    # 2) Use token to access /profile
    rv2 = client.get('/profile', headers={"Authorization": f"Bearer {token}"})
    assert rv2.status_code == 200, f"Profile falhou: {rv2.data}"
    profile = rv2.get_json()
    assert 'email' in profile and profile['email'] == login_payload['email']
