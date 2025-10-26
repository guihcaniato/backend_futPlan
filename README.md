# futPlan — Instruções de execução

Este repositório contém uma API Flask (futPlan) com autenticação JWT. Este README descreve como configurar o ambiente, executar o servidor e exemplos de chamadas usando PowerShell.

## Requisitos

- Python 3.10+ (um virtualenv é recomendado)
- MySQL acessível com a schema esperada pelo projeto
- Arquivo `requirements.txt` presente no projeto

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto contendo pelo menos as variáveis abaixo:

Exemplo mínimo (ajuste conforme seu ambiente):

JWT_SECRET_KEY=uma_chave_secreta_segura_aqui
DB_URL=mysql+mysqlconnector://usuario:senha@host:3306/nome_do_banco
# Alternativamente, se seu `config.py` aceitar partes individuais, forneça DB_USER/DB_PASSWORD/DB_HOST/DB_NAME. O código exige `JWT_SECRET_KEY` e `DB_PASSWORD`.

OBS: O `config.py` do projeto fará checagens e levantará um erro se `JWT_SECRET_KEY` ou `DB_PASSWORD` estiverem ausentes.

## Instalação (PowerShell)

# criar e ativar venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# instalar dependências
pip install -r requirements.txt

## Executar a aplicação (PowerShell)

# a partir da raiz do projeto
& .\venv\Scripts\python.exe .\app.py

A aplicação por padrão escuta em http://127.0.0.1:5000

## Exemplos de chamadas (PowerShell)

1) Criar usuário

$body = @{ nome = 'test_user'; email = 'test_user@example.com'; senha = 'Test1234!' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/usuarios -Body $body -ContentType 'application/json'

2) Login (recebe `access_token`)

$loginBody = @{ email = 'test_user@example.com'; senha = 'Test1234!' } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/login -Body $loginBody -ContentType 'application/json' -UseBasicParsing
$token = $login.access_token

3) Chamar rota protegida `/profile` com token

Invoke-RestMethod -Method Get -Uri http://127.0.0.1:5000/profile -Headers @{ Authorization = "Bearer $token" } -UseBasicParsing

Observações:
- O servidor aceita o cabeçalho `Authorization: Bearer <token>`; também há suporte para fornecer apenas o token no cabeçalho (sem prefixo `Bearer`).
- Se você receber erro do PyJWT do tipo "Subject must be a string", regenere o token com a versão atual do código (o `sub` no JWT é serializado como string). Certifique-se de usar a mesma `JWT_SECRET_KEY` que foi usada para gerar o token.

## Troubleshooting rápido

- ModuleNotFoundError: No module named 'dotenv' -> execute `pip install python-dotenv` ou instale via `requirements.txt`.
- Erro de banco (IntegrityError: Duplicate entry ...) -> usuário já existe; use outro email ou remova o registro de teste.
- Erro 401/Invalid token -> confirme `JWT_SECRET_KEY` e verifique se o token não expirou.

## Próximos passos sugeridos

- Mover rotas restantes para o pacote `routes/` (algumas já foram movidas: `auth` e `users`).
- Adicionar testes automatizados (pytest) e um `README` com exemplos de CI.


---
Arquivo gerado automaticamente pelo assistente. Se quiser, eu posso ajustar exemplos (curl, Postman) ou adicionar um `docker-compose` para facilitar testes locais.