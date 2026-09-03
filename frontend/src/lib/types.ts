/**
 * RevenueOS TypeScript Definitions & Protocol Schemas
 */

export type ProtocolVersion = "v1";

export type ClientMessageType =
  | "ping"
  | "revenue.list"
  | "revenue.details"
  | "recovery.analyze"
  | "recovery.execute"
  | "decision.explain"
  | "metrics.summary";

export type ServerMessageType =
  | "pong"
  | "revenue.list.response"
  | "revenue.details.response"
  | "revenue.updated"
  | "analysis.started"
  | "analysis.completed"
  | "recovery.approved"
  | "recovery.blocked"
  | "recovery.executed"
  | "payment.updated"
  | "payment_link.updated"
  | "decision.created"
  | "decision.explain.response"
  | "metrics.summary.response"
  | "metrics.updated"
  | "error";

export interface ProtocolError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ClientMessage<T = unknown> {
  protocolVersion: ProtocolVersion;
  requestId: string;
  type: ClientMessageType;
  timestamp: string;
  payload: T;
}

export interface ServerMessage<T = unknown> {
  protocolVersion: ProtocolVersion;
  requestId?: string;
  type: ServerMessageType;
  timestamp: string;
  payload?: T;
  error?: ProtocolError;
}

export type ConnectionState =
  | "DISCONNECTED"
  | "CONNECTING"
  | "CONNECTED"
  | "STALE"
  | "ERROR";

export interface UserContext {
  id: string;
  username: string;
  role: string;
}

export interface MetricSummary {
  revenueAtRiskPaise: number;
  expectedRecoverablePaise: number;
  actuallyRecoveredPaise: number;
  incrementalRevenuePaise: number;
  recoveryRate: number;
  activeOpportunities: number;
}

export interface Opportunity {
  paymentId: string;
  amountPaise: number;
  currency: string;
  status: string;
  failureCategory: string;
  failureReason: string;
  retryCount: number;
  maxRetries: number;
  recoverabilityScore: number;
  expectedRecoveryValuePaise: number;
  priority: "HIGH" | "MEDIUM" | "LOW";
  recoveryStatus: string;
  createdAt: string;
}

export interface BrainRecommendation {
  action: "RETRY" | "PAYMENT_LINK" | "REMINDER" | "STOP";
  confidence: number;
  expectedRecoveryValuePaise: number;
  reason: string;
  supportingFactors: string[];
  riskFactors: string[];
  reasoningSummary: string;
}

export interface RuleEvaluation {
  ruleName: string;
  passed: boolean;
  reason: string;
}

export interface PolicyVerdict {
  status: "APPROVED" | "BLOCKED";
  authorizedAction?: string | null;
  blockingRule?: string | null;
  blockingReason?: string | null;
  rulesEvaluated: RuleEvaluation[];
  evaluatedAt: string;
}

export interface DecisionRecord {
  decisionId: string;
  paymentId: string;
  modelVersion: string;
  aiRecommendation: BrainRecommendation;
  policyDecision: PolicyVerdict;
  createdAt: string;
}
