import { useCallback, useEffect, useMemo, useState } from "react";
import UploadScreen from "./components/UploadScreen";
import AnalysisResult from "./components/AnalysisResult";
import LoginScreen from "./components/LoginScreen";
import ContractListScreen from "./components/ContractListScreen";
import Sidebar from "./components/Sidebar";
import { shellMainClass, useSidebarCollapsed } from "./lib/sidebarShell";
import { uploadContract, analyzeContract, listContracts } from "./api";
import { useAuth } from "./useAuth";

export default function App() {
  const { session, loading, signOut } = useAuth();
  const [statusText, setStatusText] = useState(null);
  const [phase, setPhase] = useState(null); // "upload" | "analyze" while a new contract is processed
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [view, setView] = useState("list");
  const [analysisTab, setAnalysisTab] = useState("report");
  // Switch to the report tab whenever a different analysis result is shown
  // (state adjusted during render instead of in an effect).
  const [seenContractId, setSeenContractId] = useState(undefined);
  if (seenContractId !== result?.contractId) {
    setSeenContractId(result?.contractId);
    if (result) setAnalysisTab("report");
  }
  const [contracts, setContracts] = useState([]);
  const [contractsLoading, setContractsLoading] = useState(true);
  const [contractsError, setContractsError] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useSidebarCollapsed(false);

  const refreshContracts = useCallback(async () => {
    try {
      const res = await listContracts();
      setContracts(res.contracts || []);
      setContractsError(null);
    } catch (err) {
      setContractsError(err.message || "Không tải được danh sách hợp đồng.");
    } finally {
      setContractsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    listContracts()
      .then((res) => {
        if (cancelled) return;
        setContracts(res.contracts || []);
        setContractsError(null);
      })
      .catch((err) => {
        if (!cancelled) setContractsError(err.message || "Không tải được danh sách hợp đồng.");
      })
      .finally(() => {
        if (!cancelled) setContractsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  const handleSubmit = async (file, provider) => {
    setError(null);
    try {
      setPhase("upload");
      setStatusText("Đang tải file lên...");
      const upload = await uploadContract(file);

      setPhase("analyze");
      setStatusText("Đang chạy AI phân tích rủi ro & sai luật...");
      const analyzed = await analyzeContract(upload.contract_id, provider);

      setContracts((prev) => [
        {
          contract_id: upload.contract_id,
          filename: upload.filename,
          status: "analyzed",
          chunk_count: upload.chunk_count,
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setResult({
        contractId: upload.contract_id,
        filename: upload.filename,
        analysis: analyzed.analysis,
        risks: analyzed.risks,
        provider,
      });
      setView("list");
    } catch (err) {
      setError(err.message || "Đã xảy ra lỗi khi phân tích hợp đồng.");
      refreshContracts(); // the file may already be stored even though the analysis failed
    } finally {
      setStatusText(null);
      setPhase(null);
    }
  };

  const handleReanalyze = async () => {
    if (!result) return;
    setError(null);
    setStatusText("AI đang phân tích lại hợp đồng (khoảng 30–90 giây)...");
    try {
      const analyzed = await analyzeContract(result.contractId, result.provider, true);
      setResult((prev) => ({ ...prev, analysis: analyzed.analysis, risks: analyzed.risks }));
    } catch (err) {
      setError(err.message || "Không phân tích lại được hợp đồng này.");
    } finally {
      setStatusText(null);
    }
  };

  const handleOpenContract = async (contract) => {
    setError(null);
    setStatusText("Đang mở kết quả. Nếu kết quả cũ chưa đầy đủ, AI sẽ phân tích lại (có thể mất ~1 phút)...");
    try {
      const analyzed = await analyzeContract(contract.contract_id);
      setResult({
        contractId: contract.contract_id,
        filename: contract.filename,
        analysis: analyzed.analysis,
        risks: analyzed.risks,
      });
    } catch (err) {
      setError(err.message || "Không mở được hợp đồng này.");
    } finally {
      setStatusText(null);
    }
  };

  const goList = () => {
    setResult(null);
    setError(null);
    setView("list");
    refreshContracts();
  };

  const goUpload = () => {
    setResult(null);
    setError(null);
    setView("upload");
  };

  const issueCount = useMemo(() => {
    if (!result?.risks) return 0;
    return result.risks.filter((r) => r.severity === "critical" || r.severity === "warning").length;
  }, [result]);

  if (loading) {
    return <div className="min-h-screen bg-paper" />;
  }

  if (!session) {
    return <LoginScreen />;
  }

  const activeNav = result ? "analysis" : view;
  const mainClass = shellMainClass(sidebarCollapsed);

  return (
    <div className="min-h-screen bg-paper text-ink flex">
      <Sidebar
        activeNav={activeNav}
        analysisTab={analysisTab}
        hasAnalysis={Boolean(result)}
        issueCount={issueCount}
        onGoList={goList}
        onGoUpload={goUpload}
        onAnalysisTab={(tab) => {
          if (!result) return;
          setAnalysisTab(tab);
        }}
        onSignOut={signOut}
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />

      {result ? (
        <AnalysisResult
          contractId={result.contractId}
          filename={result.filename}
          analysis={result.analysis}
          risks={result.risks}
          provider={result.provider}
          activeTab={analysisTab}
          onTabChange={setAnalysisTab}
          onGoList={goList}
          onReanalyze={handleReanalyze}
          busyText={statusText}
          error={error}
          mainClassName={mainClass}
        />
      ) : view === "upload" ? (
        <UploadScreen
          onSubmit={handleSubmit}
          statusText={statusText}
          phase={phase}
          error={error}
          mainClassName={mainClass}
        />
      ) : (
        <ContractListScreen
          contracts={contracts}
          loading={contractsLoading}
          loadError={contractsError}
          onRetry={refreshContracts}
          onUpload={goUpload}
          statusText={statusText}
          error={error}
          onOpenContract={handleOpenContract}
          mainClassName={mainClass}
        />
      )}
    </div>
  );
}
