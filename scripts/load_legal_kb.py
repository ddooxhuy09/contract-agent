import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import logger
from app.knowledge_base.loader import load_legal_documents


def main():
    logger.info("Starting legal knowledge base loading...")
    total = load_legal_documents()
    logger.info(f"Legal KB loading complete. Total chunks added: {total}")


if __name__ == "__main__":
    main()
