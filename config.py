import os

# Verifica se está rodando no Render
if os.getenv("RENDER") == "true":
    DATABASE_PATH = "/opt/render/project-data/empresa.db"  # Pasta segura no Render
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "empresa.db")  # Local padrão da sua máquina

SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = "sua_chave_secreta"

# Garante que a pasta existe (importante pro Render)
if "render" in DATABASE_PATH:
    os.makedirs("/opt/render/project-data", exist_ok=True)