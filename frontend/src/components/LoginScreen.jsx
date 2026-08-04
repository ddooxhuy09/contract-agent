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
        <div className="mb-6">
          <p className="text-[1.125rem] font-medium text-ink tracking-tight">ContractLens</p>
          <p className="ui-text text-ink-muted mt-1">
            {mode === "signin" ? "Đăng nhập để rà soát hợp đồng" : "Tạo tài khoản mới"}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-paper-raised border border-rule rounded-md p-4 shadow-sm flex flex-col gap-3"
        >
          <div>
            <label className="block text-[0.75rem] font-medium text-ink-muted mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-rule bg-paper text-ink ui-text focus:outline-none focus:border-quiet"
              placeholder="ban@congty.com"
            />
          </div>
          <div>
            <label className="block text-[0.75rem] font-medium text-ink-muted mb-1" htmlFor="password">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-rule bg-paper text-ink ui-text focus:outline-none focus:border-quiet"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="text-stamp text-[0.75rem] font-medium">{error}</p>}
          {info && <p className="text-ok text-[0.75rem] font-medium">{info}</p>}

          <button
            type="submit"
            disabled={busy}
            className="mt-1 px-4 py-2 bg-ink text-paper-raised text-[0.75rem] font-medium rounded-md hover:bg-ink/90 transition-colors disabled:opacity-50"
          >
            {busy ? "Đang xử lý..." : mode === "signin" ? "Đăng nhập" : "Đăng ký"}
          </button>
        </form>

        <p className="mt-3 ui-text text-ink-muted">
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
