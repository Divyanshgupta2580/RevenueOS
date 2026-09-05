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
  | "analysis.stage"
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
  | "CONNECTED"
  | "RECONNECTING"
  | "OFFLINE"
  | "AUTH_FAILED"
  | "SERVER_FAILED"
  | "CLOSED_INTENTIONALLY"
  | "STALE"
  | "ERROR";

export interface UserContext {
  id: string;
  username: string;
  role: string;
}

export interface StrategyMetric {
  strategy: string;
  sampleSize: number;
  observedRecoveries: number;
  observedRecoveryRate: number;
  attributionStatus: string;
}

export interface FunnelStage {
  stage: string;
  count: number;
  description: string;
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
  observedTransactions?: number;
  observedRecoveries?: number;
  isSampleSizeSufficient?: boolean;
  attributionConfidence?: string;
  attributionStatus?: string;
  baselineAssumption?: string;
  baselineComparison?: string;
  statisticalSignificance?: string;
  sampleSizeHonestNote?: string;
  productionMerchantRecovery?: string;
  strategyBreakdown?: StrategyMetric[];
  funnel?: FunnelStage[];
  historicalTrendAvailable?: boolean;
  historicalTrendReason?: string;
}

export interface EvidenceSummary {
  verifiedFacts: {
    status: string;
    amount: string;
    currency: string;
    failureCategory: string;
    failureReason: string;
    paymentMethod: string;
    captured: boolean;
  };
  backendCalculations: {
    recoverabilityScore: number;
    expectedRecoveryPaise: number;
    formattedERV: string;
    estimatedProbability: number;
    paymentAge: string;
  };
  historicalEvidence: {
    customerId: string;
    customerSuccessfulPayments: number;
    customerFailedPayments: number;
    recoveryAttempts: number;
  };
  policyConstraints: {
    maxRetries: number;
    cooldownSeconds: number;
    allowedActions: string[];
    maxAmountPaise: number;
  };
  systemState: {
    isTestMode: boolean;
    duplicateProtectionActive: boolean;
    paymentLinkApiAvailable: boolean;
    simulatedRetryAvailable: boolean;
  };
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
  decisionId?: string;
  rulesEvaluated?: RuleEvaluation[];
  policyVerdict?: PolicyVerdict;
  evidenceSummary?: EvidenceSummary;
  isFallback?: boolean;
  decisionGeneratedSeconds?: number;
  aiTelemetry?: DecisionTelemetry;
  createdAt: string;
  updatedAt?: string;
}

export interface DecisionTelemetry {
  context_build_ms?: number;
  gemini_request_ms?: number;
  schema_validation_ms?: number;
  policy_validation_ms?: number;
  persistence_ms?: number;
  total_decision_ms?: number;
}

export interface BrainRecommendation {
  action: "RETRY" | "PAYMENT_LINK" | "REMINDER" | "STOP";
  confidence: number;
  expectedRecoveryValuePaise: number;
  expected_recovery_value_paise?: number;
  reason: string;
  supportingFactors: string[];
  riskFactors: string[];
  reasoningSummary: string;
  latency_ms?: number;
  is_fallback?: boolean;
  fallback_reason?: string;
  telemetry?: DecisionTelemetry;
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

export interface AuditTimelineItem {
  stage: string;
  title: string;
  status: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface DecisionRecord {
  decisionId: string;
  paymentId: string;
  modelVersion: string;
  endpoint?: string;
  requestId?: string;
  paymentSnapshot?: {
    paymentId?: string;
    orderId?: string;
    customerId?: string;
    customerEmail?: string;
    amount?: number;
    currency?: string;
    status?: string;
    failureCategory?: string;
    failureReason?: string;
    method?: string;
    retryCount?: number;
    maxRetriesAllowed?: number;
    createdAt?: string;
  };
  evidenceSummary?: {
    verifiedFacts?: {
      status?: string;
      amount?: string | number;
      currency?: string;
      failureCategory?: string;
      failureReason?: string;
      paymentMethod?: string;
      captured?: boolean;
    };
    backendCalculations?: {
      recoverabilityScore?: number;
      expectedRecoveryPaise?: number;
      formattedERV?: string;
      estimatedProbability?: number;
      paymentAge?: string;
    };
    historicalEvidence?: {
      customerId?: string;
      customerSuccessfulPayments?: number;
      customerFailedPayments?: number;
      recoveryAttempts?: number;
    };
    policyConstraints?: {
      maxRetries?: number;
      cooldownSeconds?: number;
      allowedActions?: string[];
      maxAmountPaise?: number;
    };
    systemState?: {
      isTestMode?: boolean;
      duplicateProtectionActive?: boolean;
      paymentLinkApiAvailable?: boolean;
      simulatedRetryAvailable?: boolean;
    };
  };
  aiRecommendation: BrainRecommendation;
  policyDecision: PolicyVerdict;
  executionStatus?: "PENDING" | "EXECUTED" | "BLOCKED" | "FAILED" | string;
  executionResult?: Record<string, unknown> | null;
  executionLatencyMs?: number | null;
  executedAt?: string | null;
  outcome?: "PENDING" | "RECOVERED" | "FAILED" | "BLOCKED_BY_POLICY" | string;
  outcomeActualPaise?: number | null;
  outcomeAt?: string | null;
  auditTimeline?: AuditTimelineItem[];
  createdAt: string;
  updatedAt?: string;
  decision_id?: string;
  payment_id?: string;
  model_version?: string;
  request_id?: string;
  payment_snapshot?: Record<string, unknown>;
  evidence_summary?: Record<string, unknown>;
  ai_recommendation?: BrainRecommendation;
  policy_decision?: PolicyVerdict;
  execution_status?: string;
  execution_result?: Record<string, unknown> | null;
  execution_latency_ms?: number | null;
  executed_at?: string | null;
  outcome_actual_paise?: number | null;
  outcome_at?: string | null;
  audit_timeline?: AuditTimelineItem[];
  created_at?: string;
}

export interface ExplanationData {
  decision_id?: string;
  explanation?: string;
  key_factors?: string[];
  policy_alignment?: string;
  counterfactual?: string;
  counterfactuals?: string[];
  outcome_assessment?: string;
  latency_ms?: number;
  summary?: string;
  decisionFactors?: string[];
  policyAlignment?: string;
  confidenceAssessment?: string;
}
