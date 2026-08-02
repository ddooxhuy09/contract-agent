import os
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "auto")
DATABASE_URL = os.getenv("DATABASE_URL", "")
VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", "data/vector_store")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "data/uploads")
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.6"))
LEGAL_KB_BATCH_SIZE = int(os.getenv("LEGAL_KB_BATCH_SIZE", "256"))
LEGAL_KB_ACTIVE_ONLY = os.getenv("LEGAL_KB_ACTIVE_ONLY", "true").lower() == "true"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "contractlens123")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 ngay

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("contractlens")

if not JWT_SECRET_KEY:
    import secrets
    JWT_SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET_KEY chua duoc dat trong .env - dang dung khoa ngau nhien "
        "(session se mat hieu luc moi lan restart server). Dat JWT_SECRET_KEY co dinh trong .env cho production."
    )
