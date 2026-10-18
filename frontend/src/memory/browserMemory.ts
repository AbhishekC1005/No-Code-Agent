export interface VectorDoc {
  id: string;
  text: string;
  metadata: Record<string, any>;
  embedding: number[];
}

export interface ThreadCheckpoint {
  threadId: string;
  step: number;
  nodeId: string;
  state: Record<string, any>;
  timestamp: string;
}

const VECTOR_STORAGE_KEY = "FLOWGRAPH_BROWSER_VECTOR_STORE";
const CHECKPOINT_STORAGE_KEY = "FLOWGRAPH_BROWSER_CHECKPOINTS";

// Deterministic local embedding fallback (32-dim bag-of-ngrams) so vector search works offline in browser
export function computeLocalBrowserEmbedding(text: string): number[] {
  const vec = new Array(32).fill(0);
  const clean = text.toLowerCase();
  for (let i = 0; i < clean.length; i++) {
    const code = clean.charCodeAt(i);
    vec[code % 32] += 1;
    if (i < clean.length - 1) {
      vec[(code + clean.charCodeAt(i + 1)) % 32] += 0.5;
    }
  }
  const norm = Math.sqrt(vec.reduce((acc: number, v: number) => acc + v * v, 0)) || 1;
  return vec.map((v: number) => +(v / norm).toFixed(4));
}

export function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB) || 1);
}

export class BrowserMemoryHarness {
  static getDocuments(): VectorDoc[] {
    try {
      const raw = localStorage.getItem(VECTOR_STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    // Seed default knowledge chunks so RAG works immediately out of the box
    const defaults: VectorDoc[] = [
      {
        id: "doc_1",
        text: "Enterprise API tokens can be reset in Settings -> Security -> Rotate Key. Tokens expire every 90 days.",
        metadata: { source: "security_handbook.pdf" },
        embedding: computeLocalBrowserEmbedding(
          "Enterprise API tokens can be reset in Settings Security Rotate Key"
        ),
      },
      {
        id: "doc_2",
        text: "Refunds for annual SaaS plans are processed within 14 days of billing via the Stripe Customer Portal.",
        metadata: { source: "billing_policy.md" },
        embedding: computeLocalBrowserEmbedding(
          "Refunds for annual SaaS plans processed within 14 days Stripe"
        ),
      },
      {
        id: "doc_3",
        text: "LangGraph checkpointers persist AgentState at every superstep using PostgresSaver or MongoDBSaver.",
        metadata: { source: "architecture_spec.md" },
        embedding: computeLocalBrowserEmbedding(
          "LangGraph checkpointers persist AgentState PostgresSaver MongoDBSaver"
        ),
      },
    ];
    localStorage.setItem(VECTOR_STORAGE_KEY, JSON.stringify(defaults));
    return defaults;
  }

  static addDocument(text: string, source = "user_upload.txt"): VectorDoc {
    const docs = this.getDocuments();
    const newDoc: VectorDoc = {
      id: `doc_${Date.now()}`,
      text,
      metadata: { source },
      embedding: computeLocalBrowserEmbedding(text),
    };
    const updated = [newDoc, ...docs];
    localStorage.setItem(VECTOR_STORAGE_KEY, JSON.stringify(updated));
    return newDoc;
  }

  static searchSimilar(query: string, topK = 2): { doc: VectorDoc; score: number }[] {
    const qVec = computeLocalBrowserEmbedding(query);
    const docs = this.getDocuments();
    return docs
      .map((doc) => ({
        doc,
        score: +cosineSimilarity(qVec, doc.embedding).toFixed(3),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);
  }

  static saveCheckpoint(cp: ThreadCheckpoint) {
    const list = this.getCheckpoints(cp.threadId);
    list.push(cp);
    localStorage.setItem(`${CHECKPOINT_STORAGE_KEY}_${cp.threadId}`, JSON.stringify(list));
  }

  static getCheckpoints(threadId: string): ThreadCheckpoint[] {
    try {
      const raw = localStorage.getItem(`${CHECKPOINT_STORAGE_KEY}_${threadId}`);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}
