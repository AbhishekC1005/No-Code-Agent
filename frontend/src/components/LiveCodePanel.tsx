import { useState, useRef, useEffect } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import {
  Code,
  Copy,
  Check,
  Download,
  ChevronRight,
  AlertTriangle,
  FileCode,
  Layers,
  Wrench,
  Server,
  FileText,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

const FILE_ICONS: Record<string, any> = {
  "graph.py": Layers,
  "nodes.py": Code,
  "state.py": FileCode,
  "tools.py": Wrench,
  "main.py": Server,
  "langgraph.json": FileText,
  "requirements.txt": FileText,
};

export function LiveCodePanel() {
  const isCodePanelOpen = useGraphStore((s) => s.isCodePanelOpen);
  const setCodePanelOpen = useGraphStore((s) => s.setCodePanelOpen);
  const codePanelWidth = useGraphStore((s) => s.codePanelWidth);
  const setCodePanelWidth = useGraphStore((s) => s.setCodePanelWidth);
  const generatedFiles = useGraphStore((s) => s.generatedFiles);
  const activeFile = useGraphStore((s) => s.activeFile);
  const setActiveFile = useGraphStore((s) => s.setActiveFile);
  const diagnostics = useGraphStore((s) => s.diagnostics);
  const highlightedLines = useGraphStore((s) => s.highlightedLines);
  const selectCodeLine = useGraphStore((s) => s.selectCodeLine);
  const workflowId = useGraphStore((s) => s.workflowId);

  const [copied, setCopied] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);
  const isResizingRef = useRef(false);

  const files = Object.keys(generatedFiles).length > 0 ? generatedFiles : {
    "graph.py": "# Generating LangGraph code...",
  };

  const currentCode = files[activeFile] || Object.values(files)[0] || "";

  // Monaco onMount
  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Detect click on lines to select node on canvas
    editor.onMouseDown((e: any) => {
      const pos = e.target.position;
      if (pos?.lineNumber) {
        selectCodeLine(activeFile, pos.lineNumber);
      }
    });
  };

  // Synchronize sourcemap line highlighting & scrolling
  useEffect(() => {
    if (!editorRef.current || !monacoRef.current) return;
    const editor = editorRef.current;
    const monaco = monacoRef.current;

    if (highlightedLines && highlightedLines.file === activeFile) {
      const start = highlightedLines.startLine;
      const end = highlightedLines.endLine;

      // Scroll into view
      editor.revealLineInCenter(start);

      // Apply decoration with animation highlight
      const newDecorations = [
        {
          range: new monaco.Range(start, 1, end, 1),
          options: {
            isWholeLine: true,
            className: "monaco-line-highlight bg-blue-500/20 border-l-4 border-blue-500 transition-all duration-300",
            glyphMarginClassName: "bg-blue-500",
          },
        },
      ];
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, newDecorations);
    } else {
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
    }
  }, [highlightedLines, activeFile]);

  // Set editor markers from diagnostics
  useEffect(() => {
    if (!monacoRef.current || !editorRef.current) return;
    const monaco = monacoRef.current;
    const model = editorRef.current.getModel();
    if (!model) return;

    const markers = diagnostics.map((d) => ({
      severity: d.level === "error" ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: 1,
      endColumn: 100,
      message: d.message,
    }));
    monaco.editor.setModelMarkers(model, "diagnostics", markers);
  }, [diagnostics, activeFile]);

  // Copy code
  const handleCopy = () => {
    navigator.clipboard.writeText(currentCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Download project ZIP
  const handleDownload = () => {
    const id = workflowId || "default";
    window.open(`/api/v1/workflows/${id}/export/project`, "_blank");
  };

  // Resizing logic
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    const startX = e.clientX;
    const startWidth = codePanelWidth;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isResizingRef.current) return;
      const deltaX = startX - moveEvent.clientX;
      setCodePanelWidth(startWidth + deltaX);
    };

    const handleMouseUp = () => {
      isResizingRef.current = false;
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  if (!isCodePanelOpen) {
    return (
      <button
        onClick={() => setCodePanelOpen(true)}
        className="fixed right-3 bottom-3 z-30 px-3.5 py-2 rounded-xl bg-slate-900 text-white shadow-xl hover:bg-slate-800 flex items-center gap-2 text-xs font-semibold cursor-pointer transition-all"
      >
        <Code className="w-4 h-4 text-blue-400" />
        <span>View LangGraph Code</span>
      </button>
    );
  }

  const errorsCount = diagnostics.filter((d) => d.level === "error").length;
  const warningsCount = diagnostics.filter((d) => d.level === "warning").length;

  return (
    <div
      style={{ width: `${codePanelWidth}px` }}
      className="h-full bg-slate-950 border-l border-slate-800 flex flex-col justify-between shadow-2xl relative z-20 flex-shrink-0"
    >
      {/* Resizing Handle on Left Border */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute top-0 bottom-0 left-0 w-1.5 hover:w-2 bg-transparent hover:bg-blue-500 cursor-col-resize transition-all z-30"
      />

      {/* Header Bar */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900">
        <div className="flex items-center gap-2">
          <Code className="w-4 h-4 text-blue-400" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            LangGraph Code
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-950 border border-blue-800 text-blue-400 font-mono">
            Live
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleCopy}
            title="Copy current file code"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1 transition-all cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span className="text-[11px] font-medium">{copied ? "Copied" : "Copy"}</span>
          </button>

          <button
            onClick={handleDownload}
            title="Download full project ZIP"
            className="p-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs flex items-center gap-1 transition-all cursor-pointer shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="text-[11px] font-semibold">Export ZIP</span>
          </button>

          <button
            onClick={() => setCodePanelOpen(false)}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* File Tabs */}
      <div className="flex items-center gap-1 px-2 py-1.5 bg-slate-900/60 border-b border-slate-800/80 overflow-x-auto text-xs">
        {Object.keys(files).map((fname) => {
          const Icon = FILE_ICONS[fname] || FileCode;
          const isActive = fname === activeFile;
          return (
            <button
              key={fname}
              onClick={() => setActiveFile(fname)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-mono flex items-center gap-1.5 transition-all whitespace-nowrap cursor-pointer ${
                isActive
                  ? "bg-slate-800 text-blue-400 border border-slate-700 shadow-xs font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-850"
              }`}
            >
              <Icon className="w-3 h-3" />
              <span>{fname}</span>
            </button>
          );
        })}
      </div>

      {/* Monaco Editor Container */}
      <div className="flex-1 overflow-hidden relative">
        <Editor
          height="100%"
          language={activeFile.endsWith(".json") ? "json" : activeFile.endsWith(".txt") ? "plaintext" : "python"}
          value={currentCode}
          theme="vs-dark"
          onMount={handleEditorDidMount}
          options={{
            readOnly: true,
            fontSize: 12,
            fontFamily: "Fira Code, Menlo, Monaco, 'Courier New', monospace",
            minimap: { enabled: false },
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            lineDecorationsWidth: 8,
            folding: true,
            renderLineHighlight: "all",
          }}
        />
      </div>

      {/* Diagnostics Status Footer */}
      <div className="border-t border-slate-800 bg-slate-900">
        <button
          onClick={() => setShowDiagnostics(!showDiagnostics)}
          className="w-full px-3 py-2 flex items-center justify-between text-xs text-slate-400 hover:bg-slate-850 cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle
              className={`w-3.5 h-3.5 ${
                errorsCount > 0
                  ? "text-rose-500"
                  : warningsCount > 0
                  ? "text-amber-500"
                  : "text-emerald-500"
              }`}
            />
            <span className="text-[11px] font-semibold text-slate-300">
              Diagnostics: {errorsCount} errors, {warningsCount} warnings
            </span>
          </div>
          <span className="text-[10px] text-slate-500">
            {showDiagnostics ? "Hide" : "Details"}
          </span>
        </button>

        {showDiagnostics && (
          <div className="max-h-36 overflow-y-auto p-3 space-y-1.5 border-t border-slate-800 bg-slate-950 font-mono text-[11px]">
            {diagnostics.length === 0 ? (
              <div className="text-emerald-400 text-xs">
                No issues detected. Graph topology is valid LangGraph!
              </div>
            ) : (
              diagnostics.map((d, idx) => (
                <div
                  key={idx}
                  className={`flex items-start gap-2 ${
                    d.level === "error" ? "text-rose-400" : "text-amber-400"
                  }`}
                >
                  <span className="uppercase text-[9px] font-bold px-1 rounded bg-slate-900 border border-slate-800 mt-0.5">
                    {d.level}
                  </span>
                  <span>{d.message}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
