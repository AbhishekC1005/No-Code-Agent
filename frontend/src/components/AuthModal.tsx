import { useState } from "react";
import { X, Cloud } from "lucide-react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  apiBase: string;
  onAuthSuccess: (token: string, user: { full_name: string; email: string }) => void;
}

export function AuthModal({ isOpen, onClose, apiBase, onAuthSuccess }: Props) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint =
        mode === "register" ? "/api/v1/auth/register" : "/api/v1/auth/login";
      const body =
        mode === "register"
          ? { full_name: fullName, email, password }
          : { email, password };

      const res = await fetch(`${apiBase}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed");
      }
      localStorage.setItem("STUDIO_JWT", data.access_token);
      localStorage.setItem("STUDIO_USER", JSON.stringify(data.user));
      onAuthSuccess(data.access_token, data.user);
      onClose();
    } catch (err: any) {
      setError(err.message || "Could not connect to FastAPI backend");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/20 backdrop-blur-xs flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl border border-[#E5E7EB] p-6 w-96 shadow-soft space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cloud className="w-4 h-4 text-[#3B82F6]" />
            <h3 className="text-base font-bold text-[#0F172A]">
              {mode === "register" ? "Create Cloud Account" : "Sign In to Sync"}
            </h3>
          </div>
          <button onClick={onClose} className="text-[#94A3B8] hover:text-[#0F172A]">
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-[#475569]">
          Secured with FastAPI <b>Bcrypt + JWT</b> & stored in <b>MongoDB</b>.
        </p>

        {error && (
          <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "register" && (
            <input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Full Name"
              className="w-full px-3.5 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
            />
          )}
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email address"
            className="w-full px-3.5 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
          />
          <input
            required
            type="password"
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (min 6 chars)"
            className="w-full px-3.5 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-full bg-[#3B82F6] hover:bg-blue-600 text-white text-xs font-semibold shadow-sm transition"
          >
            {loading
              ? "Authenticating..."
              : mode === "register"
              ? "Register & Sync Workspace"
              : "Login to Workspace"}
          </button>
        </form>

        <div className="text-center pt-1">
          <button
            onClick={() => setMode(mode === "register" ? "login" : "register")}
            className="text-xs text-[#3B82F6] font-medium hover:underline"
          >
            {mode === "register"
              ? "Already have an account? Login"
              : "Need an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
}
