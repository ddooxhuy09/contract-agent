import { useEffect, useMemo, useState } from "react";
import ExecutiveSummary from "./ExecutiveSummary";
import IssueList from "./IssueList";
import ContractProfile from "./ContractProfile";
import ClauseIndex from "./ClauseIndex";
import ChatTab from "./ChatTab";
import { parseIssue, normalizeRiskView, riskKey, sortRisks, dedupeRisks } from "../lib/riskDisplay";

export default function AnalysisResult({
  contractId,
  filename,
  analysis,
  risks,
  provider,
  activeTab,
  onTabChange,
  onGoList,
  mainClassName,
}) {
  const [openKey, setOpenKey] = useState(null);

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
  const okClauseCount = Math.max(
    0,
    clauseCount -
      new Set(
        actionable.map((r) => String(r.clause_ref || "").replace(/\D/g, "")).filter(Boolean),
      ).size,
  );

  const keyedRisks = useMemo(
    () => actionable.map((r, idx) => ({ ...r, key: riskKey(r, idx) })),
    [actionable],
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

  useEffect(() => {
    const firstCritical = keyedRisks.find((r) => r.severity === "critical");
    if (firstCritical) setOpenKey(firstCritical.key);
  }, [contractId]); // eslint-disable-line react-hooks/exhaustive-deps

  const openIssue = (key) => {
    onTabChange?.("report");
    setOpenKey(key);
  };

  return (
    <main className={mainClassName}>
      <header className="sticky top-0 z-30 bg-paper/90 backdrop-blur-sm border-b border-rule">
        <div className="max-w-content mx-auto w-full page-pad !py-0 h-11 md:h-12 flex items-center gap-2">
          <button
            type="button"
            onClick={onGoList}
            className="text-[0.6875rem] font-medium text-ink-muted hover:text-ink hidden sm:inline transition-colors shrink-0"
          >
            Hợp đồng
          </button>
          <span className="text-ink-faint hidden sm:inline shrink-0 text-[0.6875rem]">/</span>
          <span className="text-[0.8125rem] font-medium text-ink truncate min-w-0">{filename}</span>
        </div>
      </header>

      <div className="page-pad max-w-content mx-auto w-full">
        {activeTab === "report" && (
          <>
            <ExecutiveSummary
              criticalCount={criticalCount}
              warningCount={warningCount}
              okClauseCount={okClauseCount}
              topIssues={topIssues}
              onOpenIssue={openIssue}
            />
            <ContractProfile analysis={analysis} defaultOpen />
            <IssueList
              risks={keyedRisks}
              openKey={openKey}
              onOpenKeyChange={setOpenKey}
              clausesByNumber={clausesByNumber}
            />
            <ClauseIndex
              clauses={analysis.clauses || []}
              risksByClause={risksByClause}
              onOpenIssueKey={openIssue}
              defaultOpen={false}
            />
          </>
        )}

        {activeTab === "chat" && <ChatTab contractId={contractId} provider={provider} />}
      </div>
    </main>
  );
}
