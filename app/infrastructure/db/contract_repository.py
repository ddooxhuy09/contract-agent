from typing import Any
from uuid import UUID

from psycopg2.extras import Json

from app.domain.entities.contract import Contract
from app.infrastructure.db.connection import get_db


class PgContractRepository:
    def upsert(self, contract: Contract) -> None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO uploaded_contracts (
                        contract_id, user_id, filename, file_type, storage_key,
                        full_text, status, message, chunk_count, analysis, risks
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (contract_id) DO UPDATE SET
                        filename = EXCLUDED.filename,
                        file_type = EXCLUDED.file_type,
                        storage_key = EXCLUDED.storage_key,
                        full_text = COALESCE(EXCLUDED.full_text, uploaded_contracts.full_text),
                        status = EXCLUDED.status,
                        message = EXCLUDED.message,
                        chunk_count = EXCLUDED.chunk_count,
                        updated_at = NOW()
                    """,
                    (
                        contract.contract_id,
                        contract.user_id,
                        contract.filename,
                        contract.file_type,
                        contract.storage_key,
                        contract.full_text,
                        contract.status,
                        contract.message,
                        contract.chunk_count,
                        Json(contract.analysis) if contract.analysis is not None else None,
                        Json(contract.risks) if contract.risks is not None else None,
                    ),
                )

    def get(self, contract_id: str) -> Contract | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT contract_id, user_id, filename, file_type, storage_key, full_text,
                           status, message, chunk_count, analysis, risks, created_at, updated_at
                    FROM uploaded_contracts WHERE contract_id = %s
                    """,
                    (contract_id,),
                )
                row = cur.fetchone()
        return self._row(row) if row else None

    def get_owned(self, contract_id: str, user_id: UUID) -> Contract | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT contract_id, user_id, filename, file_type, storage_key, full_text,
                           status, message, chunk_count, analysis, risks, created_at, updated_at
                    FROM uploaded_contracts
                    WHERE contract_id = %s AND user_id = %s
                    """,
                    (contract_id, user_id),
                )
                row = cur.fetchone()
        return self._row(row) if row else None

    def list_by_user(self, user_id: UUID) -> list[Contract]:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT contract_id, user_id, filename, file_type, storage_key, full_text,
                           status, message, chunk_count, analysis, risks, created_at, updated_at
                    FROM uploaded_contracts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [self._row(r) for r in rows]

    def save_analysis(self, contract_id: str, analysis: dict[str, Any], risks: list[Any]) -> None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE uploaded_contracts
                    SET status = 'analyzed', analysis = %s, risks = %s, updated_at = NOW()
                    WHERE contract_id = %s
                    """,
                    (Json(analysis), Json(risks), contract_id),
                )

    @staticmethod
    def _row(row) -> Contract:
        return Contract(
            contract_id=row[0],
            user_id=row[1],
            filename=row[2],
            file_type=row[3],
            storage_key=row[4],
            full_text=row[5],
            status=row[6],
            message=row[7],
            chunk_count=row[8] or 0,
            analysis=row[9],
            risks=row[10],
            created_at=row[11],
            updated_at=row[12],
        )
