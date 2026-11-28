import { useState } from "react";
import { useAuth } from "../useAuth";

export default function LoginScreen() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      const { error: authError } =
        mode === "signin" ? await signIn(email, password) : await signUp(email, password);
      if (authError) {
        setError(authError.message);
      } else if (mode === "signup") {
        setInfo("Đăng ký thành công.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="mb-6 text-center">
          <span className="mx-auto w-14 h-14 rounded-2xl bg-quiet text-white flex items-center justify-center shadow-sm mb-3">
            <span className="material-symbols-outlined !text-[1.75rem]" style={{ fontVariationSettings: "'FILL' 1" }}>balance</span>
          </span>
          <p className="text-[1.5rem] font-semibold text-ink tracking-tight">ContractLens</p>
          <p className="ui-text text-ink-muted mt-1">
            {mode === "signin" ? "Đăng nhập để rà soát hợp đồng" : "Tạo tài khoản mới"}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="card p-5 sm:p-6 flex flex-col gap-4"
        >
          <div>
            <label className="block text-[0.8125rem] font-medium text-ink mb-1.5" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-paper text-ink text-[0.9375rem] focus:outline-none focus:border-quiet focus:bg-paper-raised"
              placeholder="ban@congty.com"
            />
          </div>
          <div>
            <label className="block text-[0.8125rem] font-medium text-ink mb-1.5" htmlFor="password">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={mode === "signup" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-paper text-ink text-[0.9375rem] focus:outline-none focus:border-quiet focus:bg-paper-raised"
              placeholder="••••••••"
            />
          </div>

          {error && <p role="alert" className="px-3 py-2 rounded-lg bg-stamp-soft text-stamp text-[0.8125rem] font-medium">{error}</p>}
          {info && <p className="px-3 py-2 rounded-lg bg-ok-soft text-ok text-[0.8125rem] font-medium">{info}</p>}

          <button
            type="submit"
            disabled={busy}
            className="mt-1 px-4 py-2.5 bg-quiet text-white text-[0.9375rem] font-semibold rounded-lg shadow-sm hover:bg-quiet/90 transition-colors disabled:opacity-50"
          >
            {busy ? "Đang xử lý..." : mode === "signin" ? "Đăng nhập" : "Đăng ký"}
          </button>
        </form>

        <p className="mt-4 ui-text text-ink-muted text-center">
          {mode === "signin" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button
            type="button"
            className="text-quiet font-medium hover:text-ink underline-offset-2 hover:underline"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setError(null);
              setInfo(null);
            }}
          >
            {mode === "signin" ? "Đăng ký ngay" : "Đăng nhập"}
          </button>
        </p>
      </div>
    </div>
  );
}
