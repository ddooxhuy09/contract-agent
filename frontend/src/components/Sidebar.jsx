import { useState } from "react";

/**
 * Unified app shell. Single "Tải hợp đồng mới" CTA.
 * Desktop: collapsible rail. Mobile: drawer + top bar.
 */
function Brand({ iconOnly = false }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <span className="w-9 h-9 rounded-xl bg-quiet text-white flex items-center justify-center shrink-0 shadow-sm">
        <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
          balance
        </span>
      </span>
      {!iconOnly && (
        <div className="min-w-0">
          <p className="text-[1rem] font-semibold text-ink tracking-tight truncate leading-tight">ContractLens</p>
          <p className="text-[0.75rem] text-ink-faint leading-tight">Rà soát hợp đồng</p>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  activeNav, // "list" | "upload" | "analysis"
  analysisTab, // "report" | "chat"
  onGoList,
  onGoUpload,
  onAnalysisTab,
  onSignOut,
  issueCount,
  hasAnalysis,
  collapsed,
  onCollapsedChange,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close the mobile menu when the navigation target changes
  // (state adjusted during render instead of in an effect).
  const [seenNav, setSeenNav] = useState(activeNav);
  const [seenTab, setSeenTab] = useState(analysisTab);
  if (seenNav !== activeNav || seenTab !== analysisTab) {
    setSeenNav(activeNav);
    setSeenTab(analysisTab);
    setMobileOpen(false);
  }

  const closeMobile = () => setMobileOpen(false);

  const goList = () => {
    onGoList();
    closeMobile();
  };
  const goUpload = () => {
    onGoUpload();
    closeMobile();
  };
  const goAnalysisTab = (tab) => {
    onAnalysisTab?.(tab);
    closeMobile();
  };

  const primaryNav = [
    { key: "list", label: "Hợp đồng", icon: "folder_open", onClick: goList },
  ];

  const analysisNav = hasAnalysis
    ? [
        {
          key: "report",
          label: "Báo cáo",
          icon: "assignment",
          onClick: () => goAnalysisTab("report"),
          count: issueCount,
        },
        {
          key: "chat",
          label: "Hỏi đáp",
          icon: "chat",
          onClick: () => goAnalysisTab("chat"),
        },
      ]
    : [];

  const isPrimaryActive = (key) => activeNav === key;
  const isAnalysisActive = (key) => activeNav === "analysis" && analysisTab === key;
  const uploadActive = activeNav === "upload";

  const navBtn = (item, active, compact) => (
    <button
      key={item.key}
      type="button"
      title={item.label}
      onClick={item.onClick}
      aria-current={active ? "page" : undefined}
      className={`relative flex items-center gap-3 w-full rounded-lg text-[0.875rem] font-medium transition-colors text-left ${
        compact ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
      } ${
        active ? "bg-quiet-soft text-quiet" : "text-ink-muted hover:bg-paper hover:text-ink"
      }`}
    >
      {active && !compact && (
        <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-quiet" />
      )}
      <span
        className="material-symbols-outlined !text-[1.25rem] shrink-0"
        style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
      >
        {item.icon}
      </span>
      {!compact && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {typeof item.count === "number" && item.count > 0 && (
            <span className="min-w-[1.375rem] text-center text-[0.75rem] font-semibold tabular-nums text-stamp bg-stamp-soft px-1.5 py-0.5 rounded-full">
              {item.count}
            </span>
          )}
        </>
      )}
    </button>
  );

  const navBody = (compact) => (
    <>
      <div className={`mb-3 ${compact ? "px-0" : "px-0.5"}`}>
        <button
          type="button"
          title="Tải hợp đồng mới"
          className={`w-full bg-quiet text-white py-2.5 rounded-lg text-[0.875rem] font-semibold shadow-sm hover:bg-quiet/90 transition-colors flex items-center justify-center gap-2 ${
            uploadActive ? "ring-2 ring-quiet ring-offset-2 ring-offset-paper-raised" : ""
          } ${compact ? "px-1.5" : "px-3"}`}
          onClick={goUpload}
        >
          <span className="material-symbols-outlined !text-[1.25rem]">add</span>
          {!compact && "Tải hợp đồng mới"}
        </button>
      </div>

      <nav className="flex-1 flex flex-col gap-0.5 overflow-y-auto min-h-0">
        {!compact && (
          <p className="px-3 pt-1 pb-1.5 meta-text uppercase text-ink-faint">Làm việc</p>
        )}
        {primaryNav.map((item) => navBtn(item, isPrimaryActive(item.key), compact))}

        {analysisNav.length > 0 && (
          <>
            {!compact && (
              <p className="px-3 pt-4 pb-1.5 meta-text uppercase text-ink-faint">Phân tích</p>
            )}
            {compact && <div className="my-1.5 border-t border-rule mx-1.5" />}
            {analysisNav.map((item) => navBtn(item, isAnalysisActive(item.key), compact))}
          </>
        )}
      </nav>

      <button
        type="button"
        title="Đăng xuất"
        className={`flex items-center gap-3 w-full rounded-lg text-[0.875rem] font-medium text-ink-muted hover:text-stamp hover:bg-stamp-soft/60 transition-colors text-left mt-2 border-t border-rule pt-3 ${
          compact ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
        }`}
        onClick={onSignOut}
      >
        <span className="material-symbols-outlined !text-[1.25rem]">logout</span>
        {!compact && "Đăng xuất"}
      </button>
    </>
  );

  return (
    <>
      {/* Mobile top bar */}
      <header className="md:hidden fixed top-0 inset-x-0 z-50 h-11 bg-paper-raised border-b border-rule flex items-center gap-2 px-2.5 safe-pt">
        <button
          type="button"
          aria-label="Mở menu"
          className="w-8 h-8 rounded-md flex items-center justify-center text-ink hover:bg-paper"
          onClick={() => setMobileOpen(true)}
        >
          <span className="material-symbols-outlined !text-[1.25rem]">menu</span>
        </button>
        <p className="text-[1rem] font-semibold text-ink truncate">ContractLens</p>
      </header>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Đóng menu"
          className="md:hidden fixed inset-0 z-[60] bg-ink/40"
          onClick={closeMobile}
        />
      )}
      <aside
        className={`md:hidden fixed top-0 left-0 z-[70] h-full w-[min(16.5rem,86vw)] bg-paper-raised border-r border-rule flex flex-col py-3 px-2.5 transition-transform duration-200 ease-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-hidden={!mobileOpen}
      >
        <div className="flex items-center justify-between px-1.5 mb-4">
          <Brand />
          <button
            type="button"
            aria-label="Đóng"
            className="w-8 h-8 rounded-md flex items-center justify-center text-ink-muted hover:bg-paper"
            onClick={closeMobile}
          >
            <span className="material-symbols-outlined !text-[1.125rem]">close</span>
          </button>
        </div>
        {navBody(false)}
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={`hidden md:flex fixed left-0 top-0 h-full bg-paper-raised border-r border-rule flex-col py-4 z-50 transition-[width] duration-200 ease-out ${
          collapsed ? "w-16 px-2" : "w-60 px-3"
        }`}
      >
        <div className={`flex items-center mb-5 ${collapsed ? "flex-col gap-3" : "justify-between px-0.5"}`}>
          <Brand iconOnly={collapsed} />
          <button
            type="button"
            aria-label={collapsed ? "Mở rộng menu" : "Thu gọn menu"}
            title={collapsed ? "Mở rộng" : "Thu gọn"}
            className="w-8 h-8 rounded-md flex items-center justify-center text-ink-muted hover:bg-paper hover:text-ink shrink-0"
            onClick={() => onCollapsedChange?.(!collapsed)}
          >
            <span className="material-symbols-outlined !text-[1.125rem]">
              {collapsed ? "keyboard_double_arrow_right" : "keyboard_double_arrow_left"}
            </span>
          </button>
        </div>
        {navBody(collapsed)}
      </aside>
    </>
  );
}
