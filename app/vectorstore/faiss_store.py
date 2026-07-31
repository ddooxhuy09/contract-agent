"""FAISS removed — vectors live in Postgres (pgvector)."""


class _Removed:
    def __getattr__(self, name):
        raise RuntimeError(
            "FAISS store removed. Use PgContractVectorSearch / PgLegalVectorSearch via app container."
        )


def get_contract_collection():
    return _Removed()


def get_legal_collection():
    return _Removed()
