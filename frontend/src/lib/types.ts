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
  | "decision.list"
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
  | "decision.list.response"
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
  | "RECONNECTING"
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
  baselineControlPaise?: number;
  incrementalRevenuePaise: number;
  recoveryRate: number;
  activeOpportunities: number;
  blockedActions?: number;
  observedSampleSize?: number;
  attributionConfidence?: string;
  baselineAssumption?: string;
  baselineComparison?: string;
  statisticalSignificance?: string;
  sampleSizeHonestNote?: string;
}

export interface Opportunity {
  paymentId: string;
  orderId?: string;
  customerId?: string;
  customerEmail?: string;
  customerMasked?: string;
  amountPaise: number;
  currency: string;
  status: string;
  failureCategory: string;
  failureReason: string;
  retryCount: number;
  maxRetries: number;
  paymentAge?: string;
  recoverabilityScore: number;
  expectedRecoveryValuePaise: number;
  recommendedIntervention?: string;
  heuristicRecommendedAction?: string;
  aiConfidence?: number;
  lastAction?: string;
  nextEligibleAction?: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  policyStatus?: "APPROVED" | "BLOCKED";
  policyReason?: string;
  recoveryStatus: string;
  createdAt: string;
  updatedAt?: string;
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
