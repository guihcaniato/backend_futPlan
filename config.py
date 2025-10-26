import os
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# Variáveis de configuração esperadas no .env
DB_PASSWORD = os.getenv("DB_PASSWORD")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY não definida no arquivo .env")
if not DB_PASSWORD:
    raise RuntimeError("DB_PASSWORD não definida no arquivo .env")

# String de conexão com o banco de dados
DB_URL = f"mysql+mysqlconnector://root:{DB_PASSWORD}@localhost/futPlan"
