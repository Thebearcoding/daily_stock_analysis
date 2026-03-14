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
