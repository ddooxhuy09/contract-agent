import { useEffect, useState } from "react";
import UploadScreen from "./components/UploadScreen";
import AnalysisResult from "./components/AnalysisResult";
import LoginScreen from "./components/LoginScreen";
import ContractListScreen from "./components/ContractListScreen";
import { uploadContract, analyzeContract, listContracts } from "./api";
import { useAuth } from "./useAuth";

export default function App() {
  const { session, loading, signOut } = useAuth();
  const [statusText, setStatusText] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [view, setView] = useState("list"); // "list" | "upload"
  const [contracts, setContracts] = useState([]);
  const [contractsLoading, setContractsLoading] = useState(true);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    listContracts()
      .then((res) => {
        if (!cancelled) setContracts(res.contracts || []);
      })
      .catch(() => {
        if (!cancelled) setContracts([]);
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
      setStatusText("Đang tải file lên...");
      const upload = await uploadContract(file);

      setStatusText("Đang chạy AI phân tích rủi ro & sai luật...");
      const analyzed = await analyzeContract(upload.contract_id, provider);

      setContracts((prev) => [
        { contract_id: upload.contract_id, filename: upload.filename, status: "analyzed", chunk_count: upload.chunk_count, created_at: new Date().toISOString() },
        ...prev,
      ]);
      setResult({
        contractId: upload.contract_id,
        filename: upload.filename,
        analysis: analyzed.analysis,
        risks: analyzed.risks,
        provider,
      });
    } catch (err) {
      setError(err.message || "Đã xảy ra lỗi khi phân tích hợp đồng.");
    } finally {
      setStatusText(null);
    }
  };

  const handleOpenContract = async (contract) => {
    setError(null);
    setStatusText("Đang tải kết quả phân tích...");
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

  const backToList = () => {
    setResult(null);
    setError(null);
    setView("list");
  };

  if (loading) {
    return <div className="min-h-screen bg-background" />;
  }

  if (!session) {
    return <LoginScreen />;
  }

  if (result) {
    return (
      <AnalysisResult
        contractId={result.contractId}
        filename={result.filename}
        analysis={result.analysis}
        risks={result.risks}
        provider={result.provider}
        onNewUpload={backToList}
        onSignOut={signOut}
      />
    );
  }

  if (view === "upload") {
    return (
      <UploadScreen
        onSubmit={handleSubmit}
        statusText={statusText}
        error={error}
        onSignOut={signOut}
        onBack={() => setView("list")}
      />
    );
  }

  return (
    <ContractListScreen
      contracts={contracts}
      loading={contractsLoading}
      statusText={statusText}
      error={error}
      onOpenContract={handleOpenContract}
      onNewUpload={() => setView("upload")}
      onSignOut={signOut}
    />
  );
}
