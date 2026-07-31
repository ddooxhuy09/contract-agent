from app.domain.entities.contract import ContractChunk
from app.infrastructure.db.connection import get_db


class PgContractChunkRepository:
    def replace_for_contract(self, contract_id: str, chunks: list[ContractChunk]) -> None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contract_chunks WHERE contract_id = %s", (contract_id,))
                for ch in chunks:
                    cur.execute(
                        """
                        INSERT INTO contract_chunks
                            (contract_id, chunk_index, clause_number, content, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            ch.contract_id,
                            ch.chunk_index,
                            ch.clause_number,
                            ch.content,
                            ch.embedding,
                        ),
                    )

    def list_contents(self, contract_id: str) -> list[str]:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content FROM contract_chunks
                    WHERE contract_id = %s
                    ORDER BY chunk_index
                    """,
                    (contract_id,),
                )
                return [r[0] for r in cur.fetchall()]

    def get_text_by_clause(self, contract_id: str, clause_number: str) -> str | None:
        """Join parts for a Điều (same clause_number), ordered by chunk_index."""
        if not clause_number:
            return None
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content FROM contract_chunks
                    WHERE contract_id = %s AND clause_number = %s
                    ORDER BY chunk_index
                    """,
                    (contract_id, str(clause_number)),
                )
                rows = [r[0] for r in cur.fetchall() if r[0]]
        if not rows:
            return None
        return "\n".join(rows)
