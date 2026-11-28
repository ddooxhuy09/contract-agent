import { useEffect, useMemo, useState } from "react";
import ExecutiveSummary from "./ExecutiveSummary";
import IssueList from "./IssueList";
import ContractProfile from "./ContractProfile";
import ClauseIndex from "./ClauseIndex";
import ChatTab from "./ChatTab";
import AiDisclaimer from "./AiDisclaimer";
import ReportActions from "./ReportActions";
import UsageSummary from "./UsageSummary";
import { parseIssue, normalizeRiskView, riskKey, sortRisks, dedupeRisks } from "../lib/riskDisplay";

const NOT_SEEN = Symbol("not-seen");

export default function AnalysisResult({
  contractId,
  filename,
  analysis,
  risks,
  provider,
  activeTab,
  onTabChange,
  onGoList,
  onReanalyze,
  busyText,
  error,
  mainClassName,
}) {
  const [openKey, setOpenKey] = useState(null);
  const [filter, setFilter] = useState("all");

  const actionable = useMemo(
    () =>
      dedupeRisks(
        sortRisks((risks || []).filter((r) => r.severity === "critical" || r.severity === "warning")),
      ),
    [risks],
  );

  const criticalCount = actionable.filter((r) => r.severity === "critical").length;
  const warningCount = actionable.filter((r) => r.severity === "warning").length;
  const clauseCount = analysis.clauses?.length || 0;
  // Clauses the judge could not assess are neither "ổn" nor flagged: count them apart.
  const uncheckedCount = analysis.coverage?.chua_kiem || 0;
  const okClauseCount = Math.max(
    0,
    clauseCount -
      uncheckedCount -
      new Set(
        actionable.map((r) => String(r.clause_ref || "").replace(/\D/g, "")).filter(Boolean),
      ).size,
  );

  const keyedRisks = useMemo(
    () => actionable.map((r, idx) => ({ ...r, key: riskKey(r, idx) })),
    [actionable],
  );

  // "info" = drafting advice / unconfirmed keyword hits: listed under "Góp ý", not counted as risks.
  const listedRisks = useMemo(
    () => [
      ...keyedRisks,
      ...dedupeRisks((risks || []).filter((r) => r.severity === "info")).map((r, idx) => ({
        ...r,
        key: riskKey(r, keyedRisks.length + idx),
      })),
    ],
    [keyedRisks, risks],
  );

  const topIssues = useMemo(
    () =>
      keyedRisks.slice(0, 3).map((r) => {
        const view = normalizeRiskView(r);
        return {
          key: r.key,
          clauseRef: r.clause_ref || "Điều khoản",
          severity: r.severity,
          conclusion: view.title || parseIssue(r.issue).conclusion,
        };
      }),
    [keyedRisks],
  );

  const clausesByNumber = useMemo(() => {
    const map = new Map();
    for (const c of analysis.clauses || []) {
      map.set(String(c.clause_number), {
        summary: c.summary,
        title: c.title,
        text: c.summary,
      });
    }
    return map;
  }, [analysis.clauses]);

  const risksByClause = useMemo(() => {
    const map = new Map();
    for (const r of keyedRisks) {
      const num = String(r.clause_ref || "").replace(/\D/g, "");
      if (!num) continue;
      const list = map.get(num) || [];
      list.push(r);
      map.set(num, list);
    }
    return map;
  }, [keyedRisks]);

  useEffect(() => {
    if (!openKey) return;
    const el = document.getElementById(`issue-${openKey}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [openKey, activeTab]);

  // Open the first critical issue on mount and whenever the contract changes
  // (state adjusted during render instead of in an effect).
  const [seenContractId, setSeenContractId] = useState(NOT_SEEN);
  if (seenContractId !== contractId) {
    setSeenContractId(contractId);
    const firstCritical = keyedRisks.find((r) => r.severity === "critical");
    if (firstCritical) setOpenKey(firstCritical.key);
  }

  const openIssue = (key) => {
    onTabChange?.("report");
    setFilter("all");
    setOpenKey(key);
  };

  const showFiltered = (severity) => {
    setFilter(severity);
    setOpenKey(null);
    document.getElementById("issues")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className={mainClassName}>
      <header className="sticky top-11 md:top-0 z-30 bg-paper-raised/95 backdrop-blur-sm border-b border-rule">
        <div className="max-w-content mx-auto w-full page-pad !py-0 h-14 flex items-center gap-2.5">
          <button
            type="button"
            onClick={onGoList}
            aria-label="Quay lại danh sách hợp đồng"
            className="inline-flex items-center gap-1 text-[0.875rem] font-medium text-ink-muted hover:text-quiet transition-colors shrink-0"
          >
            <span className="material-symbols-outlined">arrow_back</span>
            <span className="hidden sm:inline">Hợp đồng</span>
          </button>
          <span className="text-rule-strong hidden sm:inline shrink-0">/</span>
          <span className="text-[1rem] font-semibold text-ink truncate min-w-0" title={filename}>
            {filename}
          </span>
          <ReportActions contractId={contractId} onReanalyze={onReanalyze} disabled={Boolean(busyText)} />
        </div>
        {busyText && (
          <p role="status" className="px-4 md:px-6 lg:px-8 py-2 text-[0.8125rem] font-medium text-quiet bg-quiet-soft border-t border-rule flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-quiet animate-pulse" />
            {busyText}
          </p>
        )}
        {error && (
          <p role="alert" className="px-4 md:px-6 lg:px-8 py-2 text-[0.8125rem] font-medium text-stamp bg-stamp-soft border-t border-rule">
            {error}
          </p>
        )}
      </header>

      <div className="page-pad max-w-content mx-auto w-full">
        {activeTab === "report" && (
          <>
            <AiDisclaimer className="mb-4" />
            <ExecutiveSummary
              onFilter={showFiltered}
              criticalCount={criticalCount}
              warningCount={warningCount}
              okClauseCount={okClauseCount}
              uncheckedCount={uncheckedCount}
              clauseCount={clauseCount}
              topIssues={topIssues}
              onOpenIssue={openIssue}
            />
            <IssueList
              filter={filter}
              onFilterChange={setFilter}
              risks={listedRisks}
              openKey={openKey}
              onOpenKeyChange={setOpenKey}
              clausesByNumber={clausesByNumber}
            />
            <ContractProfile analysis={analysis} defaultOpen={false} />
            <ClauseIndex
              clauses={analysis.clauses || []}
              risksByClause={risksByClause}
              onOpenIssueKey={openIssue}
              defaultOpen={false}
            />
            <UsageSummary usage={analysis.usage} />
          </>
        )}

        {activeTab === "chat" && <ChatTab contractId={contractId} provider={provider} />}
      </div>
    </main>
  );
}
