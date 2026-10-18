export type NodeCategoryKey =
  | "triggers"
  | "models"
  | "agents"
  | "tools"
  | "memory"
  | "knowledge"
  | "logic"
  | "output"
  | "plugins";

export interface CategoryTheme {
  key: NodeCategoryKey;
  label: string;
  headerBg: string;
  badgeText: string;
  dotColor: string;
  handleHex: string;
  defaultTitle: string;
  description: string;
}

export const NODE_CATEGORIES: Record<NodeCategoryKey, CategoryTheme> = {
  triggers: {
    key: "triggers",
    label: "Triggers",
    headerBg: "bg-indigo-50 border-indigo-100",
    badgeText: "text-indigo-600",
    dotColor: "bg-indigo-500",
    handleHex: "#4F46E5",
    defaultTitle: "START / Eval Trigger",
    description: "Entry point or evaluation dataset injector",
  },
  models: {
    key: "models",
    label: "Models",
    headerBg: "bg-purple-50 border-purple-100",
    badgeText: "text-purple-600",
    dotColor: "bg-purple-500",
    handleHex: "#9333EA",
    defaultTitle: "ChatOpenAI / Claude",
    description: "Direct browser BYOK LLM invocation",
  },
  agents: {
    key: "agents",
    label: "Agents",
    headerBg: "bg-rose-50 border-rose-100",
    badgeText: "text-rose-600",
    dotColor: "bg-rose-500",
    handleHex: "#E11D48",
    defaultTitle: "ReAct State Agent",
    description: "Autonomous LangGraph reasoning node",
  },
  tools: {
    key: "tools",
    label: "Tools",
    headerBg: "bg-teal-50 border-teal-100",
    badgeText: "text-teal-600",
    dotColor: "bg-teal-500",
    handleHex: "#0D9488",
    defaultTitle: "HTTP / Python @tool",
    description: "External REST API or sandboxed tool function",
  },
  memory: {
    key: "memory",
    label: "Memory",
    headerBg: "bg-amber-50 border-amber-100",
    badgeText: "text-amber-600",
    dotColor: "bg-amber-500",
    handleHex: "#D97706",
    defaultTitle: "Thread Checkpointer",
    description: "PGlite browser state / Postgres & Mongo saver",
  },
  knowledge: {
    key: "knowledge",
    label: "Knowledge",
    headerBg: "bg-sky-50 border-sky-100",
    badgeText: "text-sky-600",
    dotColor: "bg-sky-500",
    handleHex: "#0284C7",
    defaultTitle: "Vector RAG Retriever",
    description: "Pinecone, PGVector, or MongoDB Atlas Search",
  },
  logic: {
    key: "logic",
    label: "Logic",
    headerBg: "bg-pink-50 border-pink-100",
    badgeText: "text-pink-600",
    dotColor: "bg-pink-500",
    handleHex: "#DB2777",
    defaultTitle: "Conditional Edge Router",
    description: "Routes state or pauses for Human interrupt()",
  },
  output: {
    key: "output",
    label: "Output",
    headerBg: "bg-green-50 border-green-100",
    badgeText: "text-green-600",
    dotColor: "bg-green-500",
    handleHex: "#16A34A",
    defaultTitle: "END + Eval Judge",
    description: "Final graph state + trajectory assertion",
  },
  plugins: {
    key: "plugins",
    label: "Plugins",
    headerBg: "bg-violet-50 border-violet-100",
    badgeText: "text-violet-600",
    dotColor: "bg-violet-500",
    handleHex: "#7C3AED",
    defaultTitle: "MCP Server Bridge",
    description: "Model Context Protocol tool integration",
  },
};
