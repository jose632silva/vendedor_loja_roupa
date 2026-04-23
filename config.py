"""
Configurações centrais da aplicação.
Defina LLM_PROVIDER no .env para escolher o modelo:
  anthropic | openai | groq
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "products" / "images"
STATIC_DIR = BASE_DIR / "static"

# ── LLM Provider ─────────────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai":    "gpt-4o-mini",
    "groq":      "llama-3.3-70b-versatile",
}
LLM_MODEL: str = os.getenv("LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, ""))

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY:    str = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY:      str = os.getenv("GROQ_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
# SQLite por padrão; troque por postgresql+psycopg2://... para produção pesada.
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/loja.db")

# ── Server ────────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", 8000))
API_BASE_URL: str = os.getenv("API_BASE_URL", f"http://localhost:{PORT}")

# ── App ───────────────────────────────────────────────────────────────────────
STORE_NAME:    str = os.getenv("STORE_NAME", "ModaStore")
MAX_HISTORY:   int = int(os.getenv("MAX_HISTORY", 20))   # mensagens carregadas por sessão

# ── Validação mínima ──────────────────────────────────────────────────────────
def validate():
    keys = {
        "anthropic": ANTHROPIC_API_KEY,
        "openai":    OPENAI_API_KEY,
        "groq":      GROQ_API_KEY,
    }
    key = keys.get(LLM_PROVIDER, "")
    if not key:
        raise EnvironmentError(
            f"Variável de API não configurada para provider '{LLM_PROVIDER}'. "
            f"Verifique seu .env."
        )

if __name__ == "__main__":
    validate()
    print(f"✅  Provider: {LLM_PROVIDER} | Modelo: {LLM_MODEL}")
    print(f"✅  DB: {DATABASE_URL}")
