import { useState, useEffect } from "react";
import {
  X,
  Key,
  Shield,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ExternalLink,
  Eye,
  EyeOff,
  Server,
  Cpu,
  Lock,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function CredentialsModal() {
  const isCredentialsOpen = useGraphStore((s) => s.isCredentialsOpen);
  const setCredentialsOpen = useGraphStore((s) => s.setCredentialsOpen);
  const credentials = useGraphStore((s) => s.credentials);
  const loadCredentials = useGraphStore((s) => s.loadCredentials);
  const createCredential = useGraphStore((s) => s.createCredential);
  const deleteCredential = useGraphStore((s) => s.deleteCredential);
  const testCredential = useGraphStore((s) => s.testCredential);
  const testRawCredential = useGraphStore((s) => s.testRawCredential);

  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<"openai" | "anthropic" | "ollama" | "bearer" | "custom">("openai");
  const [value, setValue] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434");
  const [testUrl, setTestUrl] = useState("");
  const [headerName, setHeaderName] = useState("Authorization");

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ id?: string; success: boolean; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (isCredentialsOpen) {
      loadCredentials();
    }
  }, [isCredentialsOpen, loadCredentials]);

  if (!isCredentialsOpen) return null;

  const handleTestNew = async () => {
    if (!value.trim()) {
      setErrorMessage("Please enter a key or token to test.");
      return;
    }
    setErrorMessage("");
    setIsTesting(true);
    setTestResult(null);
    try {
      const meta: Record<string, any> = {};
      if (type === "ollama") meta.base_url = baseUrl;
      if (testUrl) meta.test_url = testUrl;
      if (headerName) meta.header_name = headerName;

      const res = await testRawCredential(type, value.trim(), meta);
      setTestResult({ success: res.success, message: res.message });
    } catch (e: any) {
      setTestResult({ success: false, message: e.message || "Test failed" });
    } finally {
      setIsTesting(false);
    }
  };

  const handleTestExisting = async (id: string) => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await testCredential(id);
      setTestResult({ id, success: res.success, message: res.message });
    } catch (e: any) {
      setTestResult({ id, success: false, message: e.message || "Test failed" });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !value.trim()) {
      setErrorMessage("Name and credential value are required.");
      return;
    }
    setErrorMessage("");
    setIsSubmitting(true);
    try {
      const meta: Record<string, any> = {};
      if (type === "ollama") meta.base_url = baseUrl;
      if (testUrl) meta.test_url = testUrl;
      if (headerName) meta.header_name = headerName;

      await createCredential(name.trim(), type, value.trim(), meta);
      setName("");
      setValue("");
      setIsCreating(false);
      setTestResult(null);
    } catch (e: any) {
      setErrorMessage(e.message || "Failed to save credential.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const getTypeIcon = (t: string) => {
    switch (t) {
      case "openai":
      case "anthropic":
        return <Cpu className="w-4 h-4 text-emerald-600" />;
      case "ollama":
        return <Server className="w-4 h-4 text-purple-600" />;
      default:
        return <Lock className="w-4 h-4 text-blue-600" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 shadow-2xs">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Generic Typed Credentials</h2>
              <p className="text-[11px] text-slate-500">
                Encrypted at rest with per-install key. Secrets are never exposed to the browser.
              </p>
            </div>
          </div>
          <button
            onClick={() => setCredentialsOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Active Global Test Banner */}
          {testResult && (
            <div
              className={`p-3.5 rounded-xl border flex items-start gap-3 text-xs ${
                testResult.success
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-rose-50 border-rose-200 text-rose-800"
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <span className="font-bold">{testResult.success ? "Verification Succeeded: " : "Verification Failed: "}</span>
                <span>{testResult.message}</span>
              </div>
            </div>
          )}

          {/* New Credential Form Toggle */}
          {!isCreating ? (
            <button
              onClick={() => {
                setIsCreating(true);
                setTestResult(null);
                setErrorMessage("");
              }}
              className="w-full py-2.5 px-4 rounded-xl border border-dashed border-blue-300 hover:border-blue-500 bg-blue-50/40 hover:bg-blue-50 text-blue-700 text-xs font-bold flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Add New Credential</span>
            </button>
          ) : (
            <form onSubmit={handleSave} className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
                <span className="text-xs font-bold text-slate-800">Add New Credential</span>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="text-slate-400 hover:text-slate-600 text-xs"
                >
                  Cancel
                </button>
              </div>

              {errorMessage && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase">Credential Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Production OpenAI Key"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800 focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase">Type</label>
                  <select
                    value={type}
                    onChange={(e: any) => setType(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800 focus:outline-none focus:border-blue-500"
                  >
                    <option value="openai">OpenAI API Key</option>
                    <option value="anthropic">Anthropic API Key</option>
                    <option value="ollama">Ollama Server URL</option>
                    <option value="bearer">HTTP Bearer Token</option>
                    <option value="custom">Custom Header / Key</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-bold text-slate-600 uppercase">
                  {type === "ollama" ? "Server URL" : "Secret Key / Token"}
                </label>
                <div className="relative">
                  <input
                    type={showSecret ? "text" : "password"}
                    placeholder={
                      type === "openai"
                        ? "sk-proj-..."
                        : type === "anthropic"
                        ? "sk-ant-..."
                        : type === "ollama"
                        ? "http://localhost:11434"
                        : "Token value"
                    }
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    className="w-full pl-3 pr-10 py-2 rounded-xl border border-slate-200 text-xs font-mono bg-white text-slate-800 focus:outline-none focus:border-blue-500"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {type === "ollama" && (
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase">Ollama Base URL</label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800"
                  />
                </div>
              )}

              {(type === "bearer" || type === "custom") && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-slate-600 uppercase">Header Name</label>
                    <input
                      type="text"
                      placeholder="Authorization"
                      value={headerName}
                      onChange={(e) => setHeaderName(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-slate-600 uppercase">Test Endpoint URL</label>
                    <input
                      type="text"
                      placeholder="https://api.example.com/health"
                      value={testUrl}
                      onChange={(e) => setTestUrl(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800"
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleTestNew}
                  disabled={isTesting}
                  className="px-3.5 py-1.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ExternalLink className="w-3.5 h-3.5" />}
                  <span>Test Connection</span>
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsCreating(false)}
                    className="px-3 py-1.5 rounded-xl text-slate-600 hover:bg-slate-200 text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-xs cursor-pointer flex items-center gap-1.5"
                  >
                    {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    <span>Save Credential</span>
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* List of Saved Credentials */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Configured Credentials ({credentials.length})
            </h3>
            {credentials.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
                <Key className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-xs font-medium text-slate-500">No credentials configured yet.</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Add an API key or bearer token to reference inside LLM and Tool nodes.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {credentials.map((c) => (
                  <div
                    key={c.id}
                    className="p-3.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white shadow-2xs flex items-center justify-between gap-3 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                        {getTypeIcon(c.type)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-800 truncate">{c.name}</span>
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600">
                            {c.type}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[11px] font-mono text-slate-400">{c.masked_value}</span>
                          <span className="text-[10px] text-slate-300">• ID: {c.id}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleTestExisting(c.id)}
                        disabled={isTesting}
                        className="px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 text-[11px] font-semibold text-slate-600 transition-colors cursor-pointer flex items-center gap-1"
                      >
                        {isTesting && testResult?.id === c.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <ExternalLink className="w-3 h-3" />
                        )}
                        <span>Test</span>
                      </button>
                      <button
                        onClick={() => deleteCredential(c.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                        title="Delete credential"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-[11px] text-slate-500">
          <span>Generated code reads keys from environment variables, never hardcodes them.</span>
          <button
            onClick={() => setCredentialsOpen(false)}
            className="px-4 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 cursor-pointer shadow-2xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
