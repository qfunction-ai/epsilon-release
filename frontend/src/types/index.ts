/**
 * TypeScript types for the Epsilon frontend.
 *
 * These mirror the Pydantic schemas in the backend (app/schemas/vulnerability.py,
 * app/schemas/auth.py) and the SSE event shapes produced by the agent stream.
 */

/** A single OWASP prevention strategy. */
export interface OwaspStrategy {
  /** OWASP strategy number from the Prevention and Mitigation Strategies section. */
  number: number
  /** Full strategy title from the OWASP document. */
  title: string
  /** Strategy description text from the OWASP document. */
  description: string
}

/** A reference to a defensive control mapped to OWASP strategies. */
export interface DefenseRef {
  /** Name or identifier of the defensive control. */
  control: string
  /** OWASP prevention strategies associated with this control. */
  owasp_strategies: OwaspStrategy[]
  /** How the control implements the strategy. */
  implementation: string
  /** Trimmed code snippet (5-10 lines) from the framework source. */
  code_snippet: string
}

/** A lightweight summary of an OWASP vulnerability entry. */
export interface VulnerabilitySummary {
  /** Unique identifier for the vulnerability entry (e.g. 'llm01:2026'). */
  id: string
  /** The OWASP category identifier (e.g. 'LLM01'). */
  owasp_id: string
  /** Human-readable title of the vulnerability. */
  title: string
  /** The OWASP edition year (e.g. 2026). */
  year: number
  /** Whether a runtime defense agent is available for this vulnerability. */
  has_runtime_defense: boolean
  /** Short summary of the runtime defense, if available. */
  defense_summary: string
}

/** A single step in an exploit walkthrough. */
export interface ExploitStep {
  /** Short action-oriented title. */
  title: string
  /** Why this step matters and what to look for. */
  instruction: string
  /** Prompt to send to the agent. Empty for observation steps. */
  prompt: string
}

/** A detailed view of an OWASP vulnerability, including examples and defenses. */
export interface VulnerabilityDetail extends VulnerabilitySummary {
  /** Full description of the vulnerability. */
  description: string
  /** Real-world examples illustrating the vulnerability. */
  real_world_examples: string[]
  /** Explanation of why this vulnerability matters. */
  why_it_matters: string
  /** Suggested prompts for the Overview tab. */
  suggested_prompts: string[]
  /** Step-by-step exploit instructions for the Exploit tab. */
  exploit_steps: ExploitStep[]
  /** References to defensive controls and OWASP strategies. */
  defense_refs: DefenseRef[]
}

/** A side-by-side comparison of vulnerable and fixed code. */
export interface CodeComparison {
  /** The vulnerable version of the code. */
  vulnerable_code: string
  /** The remediated / fixed version of the code. */
  fixed_code: string
}

/** Metadata and entries for a specific OWASP edition year. */
export interface YearInfo {
  /** The OWASP edition year (e.g. 2026). */
  year: number
  /** Whether this year corresponds to the latest OWASP edition. */
  latest: boolean
  /** Human-readable label for the OWASP edition (e.g. 'OWASP Top 10 for LLMs 2026'). */
  edition: string
  /** Vulnerability summaries included in this edition. */
  entries: VulnerabilitySummary[]
}

/** A tool call made by the agent during a chat turn. */
export interface ToolCall {
  /** Name of the tool invoked. */
  name: string
  /** Arguments passed to the tool, as a JSON string or object. */
  args: string | Record<string, unknown>
  /** Whether the tool was executed or denied. */
  status: 'executed' | 'denied'
  /** Optional status text shown to the user (e.g. '✓ sent', '✗ DENIED'). */
  statusText?: string
  /** Optional reason for denial or additional context. */
  reason?: string
}

/** A security warning emitted during an agent run. */
export interface SecurityWarning {
  /** Type of the warning (e.g. 'canary_detected', 'tool_denied'). */
  type: string
  /** Human-readable warning message. */
  message: string
  /** Alias for message — used by ChatInterface as `text`. */
  text?: string
}

/** A single message in a chat conversation. */
export interface ChatMessage {
  /** Unique message identifier. */
  id?: string
  /** Role of the message sender. */
  role: 'user' | 'assistant'
  /** Text content of the message. */
  content: string
  /** Model reasoning trace (thinking tokens), if reasoning was captured. */
  reasoning?: string
  /** Tool calls made by the agent in this message, if any. */
  toolCalls?: ToolCall[]
  /** Security warnings emitted during this message, if any. */
  securityWarnings?: SecurityWarning[]
  /** True when the run was aborted (0.16.29 run-abort); informational terminal state. */
  cancelled?: boolean
  /** Timestamp of the message (Unix epoch ms or ISO string). */
  timestamp?: number | string
}

/** A security event record from the audit log. */
export interface SecurityEvent {
  /** Unique identifier for the event. */
  id: string
  /** Timestamp of the event (ISO string). */
  timestamp: string
  /** Type of the event (e.g. 'tool_denied', 'canary_detected'). */
  event_type: string
  /** Name of the tool involved, if applicable. */
  tool_name: string
  /** Human-readable reason for the event. */
  reason: string
  /** Optional vulnerability ID associated with the event. */
  vuln_id?: string
  /** Optional agent ID associated with the event. */
  agent_id?: string
}

/** Observability overview data for the dashboard. */
export interface ObservabilityData {
  /** Total number of agent runs. */
  total_runs: number
  /** Number of completed (successful) runs. */
  completed_runs?: number
  /** Number of failed runs. */
  failed_runs?: number
  /** Success rate as a percentage (0–100). */
  success_rate: number
  /** Total number of tool calls across all runs. */
  tool_calls: number
  /** Number of tool calls that were executed. */
  tool_calls_executed?: number
  /** Number of tool calls that were denied. */
  tool_calls_denied?: number
  /** Total number of security events. */
  security_events: number
  /** Number of canary detections. */
  canary_count?: number
  /** Number of secret detections. */
  secret_count?: number
  /** Number of denied tool calls (security). */
  denied_count?: number
  /** Optional token usage breakdown. */
  token_usage?: {
    prompt_tokens: number
    completion_tokens: number
    total: number
    total_tokens?: number
    budget?: number
  }
  /** Optional tool call distribution by tool name. */
  tool_distribution?: Record<string, number>
}

/** The code state for a vulnerability — vulnerable or fixed. */
export type CodeState = 'vulnerable' | 'fixed'

/** The sidebar state dot for a vulnerability. */
export type VulnState = 'vulnerable' | 'fixed' | 'no-defense'

/** Security event type filter values. */
export type SecurityEventType =
  | 'tool_denied'
  | 'canary_detected'
  | 'secret_detected'
  | 'injection_detected'
  | 'tool_executed'
  | 'message_sent'

/** Tab names for the vulnerability detail page. */
export type TabName = 'exploit' | 'overview' | 'code' | 'defense'

/** Configuration for a vulnerability-specific defense agent. */
export interface VulnerabilityConfig {
  /** System prompt for the defense agent. */
  system_prompt: string
  /** List of tool names enabled for the defense agent. */
  tools: string[]
  /** Policy configuration governing agent behavior. */
  policy: Record<string, unknown>
  /** Whether canary detection is enabled. */
  canary: boolean
  /** Whether content validation is enabled. */
  content_validation: boolean
  /** List of document identifiers attached to the agent. */
  documents: string[]
}

/** Return type of the useChat hook. */
export interface UseChatResult {
  /** Messages in the conversation. */
  messages: ChatMessage[]
  /** Whether a stream is currently active. */
  streaming: boolean
  /** Error message, if any. */
  error: string
  /** Send a message to the agent. */
  sendMessage: (year: number, vulnId: string, codeState: CodeState, message: string) => Promise<void>
}
