export interface PriceZone {
  low: number;
  high: number;
  description: string;
}

export interface FundStrategy {
  buyZone: PriceZone;
  addZone: PriceZone;
  stopLoss: number;
  takeProfit: number;
  positionAdvice: string;
}

export interface RuleAssessment {
  entryRule: string;
  exitRule: string;
  entryReady: boolean;
  exitTriggered: boolean;
  comment: string;
}

export interface MacdSnapshot {
  dif: number;
  dea: number;
  bar: number;
  status: string;
  signal: string;
}

export interface RsiSnapshot {
  rsi6: number;
  rsi12: number;
  rsi24: number;
  status: string;
  signal: string;
}

export interface DeepAnalysisSummary {
  analysisSummary?: string | null;
  operationAdvice?: string | null;
  trendPrediction?: string | null;
  sentimentScore?: number | null;
  sentimentLabel?: string | null;
}

export interface DeepAnalysisStrategy {
  idealBuy?: number | null;
  secondaryBuy?: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
}

export interface DeepAnalysisDetails {
  newsSummary?: string | null;
  technicalAnalysis?: string | null;
  fundamentalAnalysis?: string | null;
  riskWarning?: string | null;
}

export interface DeepAnalysisPayload {
  requested: boolean;
  status: 'completed' | 'failed' | string;
  source: string;
  reportType?: string | null;
  stockCode?: string | null;
  stockName?: string | null;
  summary: DeepAnalysisSummary;
  strategy: DeepAnalysisStrategy;
  details: DeepAnalysisDetails;
  error?: string | null;
}

export interface FundAdviceResponse {
  fundCode: string;
  analysisCode: string;
  mappedFrom?: string | null;
  mappingNote?: string | null;
  fundName?: string | null;
  latestDate: string;
  dataSource?: string | null;

  action: 'buy' | 'hold' | 'wait' | 'reduce' | string;
  actionLabel: string;
  confidenceLevel: '高' | '中' | '低' | string;
  confidenceScore: number;
  trendStatus: string;
  buySignal: string;
  signalScore: number;

  currentPrice: number;
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  volumeStatus: string;
  volumeRatio5d: number;

  macd: MacdSnapshot;
  rsi: RsiSnapshot;
  ruleAssessment: RuleAssessment;
  strategy: FundStrategy;

  reasons: string[];
  riskFactors: string[];
  analysisMode: 'fast' | 'deep' | string;
  deepAnalysis?: DeepAnalysisPayload | null;
  generatedAt: string;
}

// ── Phase 5: Fund async task types ──

export interface FundTaskInfo {
  taskId: string;
  fundCode: string;
  fundName?: string | null;
  assetType: string;
  analysisMode?: string | null;
  status: string;
  progress: number;
  message?: string | null;
  error?: string | null;
  createdAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface FundTaskListResponse {
  total: number;
  pending: number;
  processing: number;
  tasks: FundTaskInfo[];
}

export interface FundTaskAccepted {
  taskId: string;
  status: string;
  message: string;
}

export interface FundTaskStatus {
  taskId: string;
  status: string;
  progress: number;
  fundCode?: string | null;
  analysisCode?: string | null;
  analysisMode?: string | null;
  recordId?: number | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  createdAt?: string | null;
}

// ── Phase 5: Fund history types ──

export interface FundHistoryItem {
  id: number;
  queryId?: string | null;
  fundCode: string;
  fundName?: string | null;
  analysisCode: string;
  analysisName?: string | null;
  analysisMode?: string | null;
  action?: string | null;
  confidenceScore?: number | null;
  createdAt: string;
}

export interface FundHistoryListResponse {
  total: number;
  page: number;
  limit: number;
  items: FundHistoryItem[];
}

export interface FundHistoryDetailResponse {
  id: number;
  queryId?: string | null;
  fundCode: string;
  fundName?: string | null;
  analysisCode: string;
  analysisName?: string | null;
  analysisMode?: string | null;
  reportType?: string | null;
  action?: string | null;
  actionLabel?: string | null;
  confidenceScore?: number | null;
  confidenceLevel?: string | null;
  strategy?: FundStrategy | null;
  reasons?: string[] | null;
  riskFactors?: string[] | null;
  ruleAssessment?: RuleAssessment | null;
  indicators?: {
    currentPrice?: number | null;
    trendStatus?: string | null;
    buySignal?: string | null;
    signalScore?: number | null;
    ma5?: number | null;
    ma10?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    volumeStatus?: string | null;
    volumeRatio5d?: number | null;
    macd?: MacdSnapshot | null;
    rsi?: RsiSnapshot | null;
  } | null;
  deepAnalysis?: DeepAnalysisPayload | null;
  mappingNote?: string | null;
  analysisSummary?: string | null;
  createdAt?: string | null;
}
