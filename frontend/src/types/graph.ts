export type StateFieldType =
  | "str"
  | "int"
  | "float"
  | "bool"
  | "list"
  | "dict"
  | "messages";

export type ReducerType =
  | "overwrite"
  | "add_messages"
  | "append"
  | "operator.add"
  | "custom";

export interface StateField {
  name: string;
  type: StateFieldType;
  reducer: ReducerType;
  default?: any;
}

export interface StateSchema {
  fields: StateField[];
  input_fields: string[];
  output_fields: string[];
}

export interface NodeRetryPolicy {
  max_retries?: number;
  delay?: number;
  backoff_factor?: number;
}

export interface NodeCachePolicy {
  enabled?: boolean;
}

export interface NodePolicy {
  retry?: NodeRetryPolicy;
  cache?: NodeCachePolicy;
  defer?: boolean;
  interrupt_before?: boolean;
  interrupt_after?: boolean;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
  config: Record<string, any>;
  policy: NodePolicy;
}

export interface EdgeCondition {
  branches?: Record<string, string>;
  path_map?: Record<string, string>;
  code?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: "normal" | "conditional";
  condition?: EdgeCondition | null;
}

export interface GraphSettings {
  checkpointer: "sqlite" | "memory" | "none";
  recursion_limit: number;
  interrupt_before: string[];
  interrupt_after: string[];
  store: Record<string, any>;
  config_fields: any[];
}

export interface SubgraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  state?: StateSchema;
  state_mapping?: Record<string, string>;
}

export interface GraphSchemaData {
  schema_version: string;
  state: StateSchema;
  nodes: GraphNode[];
  edges: GraphEdge[];
  subgraphs: Record<string, SubgraphData>;
  settings: GraphSettings;
}

export interface Diagnostic {
  level: "error" | "warning" | "info";
  node_id?: string | null;
  message: string;
}

export interface SourcemapEntry {
  file: string;
  start_line: number;
  end_line: number;
}

export interface CodegenResult {
  files: Record<string, string>;
  sourcemap: Record<string, SourcemapEntry>;
  diagnostics: Diagnostic[];
}

export interface NodeTypeField {
  name: string;
  label: string;
  type: "text" | "textarea" | "select" | "number" | "boolean" | "code";
  options?: string[];
  default?: any;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
}

export interface NodeTypeDefinition {
  type: string;
  label: string;
  category: string;
  description: string;
  color: string;
  default_config: Record<string, any>;
  fields: NodeTypeField[];
}

export interface TriggerDefinition {
  id: string;
  workflow_id: string;
  name: string;
  type: "webhook" | "cron";
  config: {
    path?: string;
    token?: string;
    cron_expression?: string;
    payload_mapping?: Record<string, any>;
    thread_id_rule?: string;
  };
  is_active: boolean;
  last_run?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface ExecutionRecord {
  id: string;
  workflow_id: string;
  thread_id: string;
  mode: string;
  status: "running" | "success" | "error" | "interrupted" | "cancelled";
  start_time: string;
  end_time?: string | null;
  total_ms?: number | null;
  error_message?: string | null;
  created_at: string;
}

