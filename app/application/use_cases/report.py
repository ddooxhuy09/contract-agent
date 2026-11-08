"""Shareable report for one analysed contract: findings plus the AI usage behind them."""

from datetime import UTC, datetime
from uuid import UUID

from app.domain.errors import NotFoundError
from app.domain.ports.repositories import ContractRepository

REPORT_VERSION = 1
_SEVERITY_LABEL = {"critical": "Nghiêm trọng", "warning": "Cần chú ý", "ok": "Ổn"}
DISCLAIMER = (
    "Kết quả phân tích và khuyến nghị của AI chỉ mang tính tham khảo, không phải tư vấn pháp lý "
    "chính thức. Vui lòng kiểm tra quy định pháp luật hiện hành và tham khảo ý kiến chuyên gia "
    "trước khi đưa ra quyết định."
)


class BuildContractReport:
    def __init__(self, contracts: ContractRepository):
        self._contracts = contracts

    def execute(self, contract_id: str, user_id: UUID) -> dict:
        contract = self._contracts.get_owned(contract_id, user_id)
        if contract is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        if not contract.analysis:
            raise NotFoundError("Hợp đồng này chưa được phân tích.")
        analysis = dict(contract.analysis)
        usage = analysis.pop("usage", None)  # reported on its own, not as a contract field
        risks = list(contract.risks or [])
        coverage = analysis.get("coverage") or {}
        by_severity = {s: sum(1 for r in risks if r.get("severity") == s) for s in _SEVERITY_LABEL}
        return {
            "report_version": REPORT_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "contract": {
                "contract_id": contract.contract_id,
                "filename": contract.filename,
                "file_type": contract.file_type,
                "uploaded_at": contract.created_at.isoformat() if contract.created_at else None,
            },
            "summary": {
                "clause_count": len(analysis.get("clauses") or []),
                "clauses_checked": coverage.get("da_kiem"),
                "clauses_unchecked": coverage.get("chua_kiem", 0),
                "findings_by_severity": by_severity,
            },
            "analysis": analysis,
            "risks": risks,
            "usage": usage,  # None for analyses saved before usage tracking existed
            "disclaimer": DISCLAIMER,
        }


def _bullets(items: list | None) -> list[str]:
    return [f"  - {item}" for item in items or [] if str(item).strip()]


def _risk_lines(risk: dict) -> list[str]:
    title = risk.get("title") or risk.get("issue") or ""
    lines = [f"### {risk.get('clause_ref', 'Điều khoản')} — {title}", ""]
    if risk.get("title") and risk.get("issue"):
        lines += [risk["issue"], ""]
    for label, key in (("Lý do", "reasons"), ("Tác động", "impact"), ("Cần làm", "actions")):
        if risk.get(key):
            lines += [f"- **{label}:**", *_bullets(risk[key])]
    if risk.get("legal_basis"):
        lines.append(f"- **Căn cứ pháp luật:** {risk['legal_basis']}")
    for cite in risk.get("legal_citations") or []:
        where = " · ".join(p for p in (cite.get("doc_number"), cite.get("location"), cite.get("status")) if p)
        lines.append(f"  - {cite.get('title', '')}" + (f" ({where})" if where else ""))
    if risk.get("recommendation"):
        lines.append(f"- **Khuyến nghị:** {risk['recommendation']}")
    if risk.get("revised_clause"):
        lines += ["- **Đề xuất sửa:**", "", f"  > {risk['revised_clause']}"]
    return [*lines, ""]


def render_markdown(report: dict) -> str:
    contract, summary, usage = report["contract"], report["summary"], report.get("usage")
    sev = summary["findings_by_severity"]
    lines = [
        f"# Báo cáo rà soát hợp đồng: {contract['filename']}",
        "",
        f"- Mã hợp đồng: `{contract['contract_id']}`",
        f"- Tải lên: {contract['uploaded_at'] or 'không rõ'}",
        f"- Xuất báo cáo: {report['generated_at']}",
        "",
        "## Tóm tắt",
        "",
        f"- Số điều khoản: {summary['clause_count']}"
        + (f" (đã kiểm {summary['clauses_checked']}, chưa kiểm {summary['clauses_unchecked']})"
           if summary["clauses_checked"] is not None else ""),
        f"- {_SEVERITY_LABEL['critical']}: {sev['critical']} · {_SEVERITY_LABEL['warning']}: {sev['warning']}",
        "",
        "## Mức sử dụng AI",
        "",
    ]
    if usage:
        lines += [
            "| Chỉ số | Giá trị |",
            "|---|---|",
            f"| Số lượt request | {usage['requests']} (lỗi: {usage['failed_requests']}) |",
            f"| Token đầu vào | {usage['input_tokens']:,} |",
            f"| Token đầu ra | {usage['output_tokens']:,} |",
            f"| Tổng token | {usage['total_tokens']:,} |",
            f"| Thời gian phân tích | {usage['duration_seconds']} giây |",
            "",
        ]
    else:
        lines += ["Không có số liệu (phân tích này được lưu trước khi hệ thống ghi nhận mức sử dụng).", ""]
    for severity in ("critical", "warning"):
        group = [r for r in report["risks"] if r.get("severity") == severity]
        if group:
            lines += [f"## {_SEVERITY_LABEL[severity]} ({len(group)})", ""]
            for risk in group:
                lines += _risk_lines(risk)
    lines += ["---", "", f"_{report['disclaimer']}_", ""]
    return "\n".join(lines)
