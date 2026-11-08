// Dogadjaji koje backend salje kroz SSE (web/server.py -> on_event iz agenata).
// Polje "agent": "planner" | "researcher:t1" | "synthesizer"; kod jednog agenta ga nema.

export type Mode = "single" | "multi";

export type AgentEvent =
  | { type: "run_start"; t: number; mode: Mode; question: string; model: string }
  | { type: "model"; t: number; agent?: string; step?: number; seconds: number; input_tokens: number;
      output_tokens: number; finish: string; provider?: string }
  | { type: "tool"; t: number; agent?: string; name: string; arguments: string; result_chars: number;
      error: boolean; returned_ids: string[] }
  | { type: "plan"; t: number; agent: "planner"; subtasks: number; tasks: { id: string; task: string }[];
      fallback?: boolean }
  | { type: "plan_error"; t: number; agent: "planner"; attempt: number; error: string }
  | { type: "start"; t: number; agent: string; task: string }
  | { type: "finish"; t: number; agent: string; stop_reason: string; seconds: number; answer: string | null }
  | { type: "error"; t: number; agent?: string; error: string }
  | ({ type: "done"; t: number } & DoneSummary);

export type DoneSummary = {
  answer: string | null;
  stop_reason: string;
  seconds: number;
  llm_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  max_input_tokens: number;
  cost: number | null;
  plan?: { id: string; task: string }[];
  plan_fallback?: boolean;
  research_seconds?: number;
};

export type Step =
  | { kind: "model"; t: number; step?: number; seconds: number; input_tokens: number; output_tokens: number;
      finish: string }
  | { kind: "tool"; t: number; name: string; arguments: string; error: boolean; returned_ids: string[] };

export type LaneStatus = "waiting" | "running" | "done" | "failed";

export type Lane = {
  id: string;            // "agent" (jedan agent) ili "researcher:t1"...
  title: string;
  task?: string;
  status: LaneStatus;
  steps: Step[];
  answer?: string | null;
  stopReason?: string;
  seconds?: number;
};

export type Question = { id: string; type: string; set: string; question_en: string; question_sr: string };
