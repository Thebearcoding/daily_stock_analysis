import React, { useState, useEffect, useRef } from 'react';
import { fundsApi } from '../api/funds';
import type { FundAdviceMode } from '../api/funds';
import type {
  FundAdviceResponse,
  FundTaskInfo,
  FundHistoryDetailResponse,
  FundHistoryItem,
} from '../types/funds';

import { Toolbar } from '../components/FundAnalysis/Toolbar';
import { HeroSummary } from '../components/FundAnalysis/HeroSummary';
import { AsyncTaskIndicator } from '../components/FundAnalysis/AsyncTaskIndicator';
import { HistoryList } from '../components/FundAnalysis/HistoryList';
import { DetailDrawer } from '../components/FundAnalysis/DetailDrawer';

const validateFundCode = (value: string): { valid: boolean; message?: string; normalized: string } => {
  const normalized = value.trim();
  if (!normalized) {
    return { valid: false, message: '请输入基金代码', normalized };
  }
  if (!/^\d{6}$/.test(normalized)) {
    return { valid: false, message: '基金代码应为 6 位数字', normalized };
  }
  return { valid: true, normalized };
};

const EMPTY_MACD = { dif: 0, dea: 0, bar: 0, status: '--', signal: '--' };
const EMPTY_RSI = { rsi6: 0, rsi12: 0, rsi24: 0, status: '--', signal: '--' };
const EMPTY_RULE = {
  entryRule: '暂无入场规则',
  exitRule: '暂无离场规则',
  entryReady: false,
  exitTriggered: false,
  comment: '暂无规则说明',
};
const EMPTY_STRATEGY = {
  buyZone: { low: 0, high: 0, description: '--' },
  addZone: { low: 0, high: 0, description: '--' },
  stopLoss: 0,
  takeProfit: 0,
  positionAdvice: '--',
};

const mapHistoryDetailToAdvice = (detail: FundHistoryDetailResponse): FundAdviceResponse => {
  const indicators = detail.indicators ?? {};

  return {
    fundCode: detail.fundCode,
    analysisCode: detail.analysisCode,
    mappedFrom: null,
    mappingNote: detail.mappingNote ?? null,
    fundName: detail.fundName ?? detail.analysisName ?? detail.fundCode,
    latestDate: detail.createdAt ? detail.createdAt.slice(0, 10) : '--',
    dataSource: null,
    action: detail.action ?? 'hold',
    actionLabel: detail.actionLabel ?? detail.action ?? '持有',
    confidenceLevel: detail.confidenceLevel ?? '中',
    confidenceScore: detail.confidenceScore ?? 0,
    trendStatus:
      indicators.trendStatus ??
      detail.deepAnalysis?.summary?.trendPrediction ??
      detail.analysisSummary ??
      '暂无趋势判断',
    buySignal: indicators.buySignal ?? '--',
    signalScore: indicators.signalScore ?? 0,
    currentPrice: indicators.currentPrice ?? 0,
    ma5: indicators.ma5 ?? 0,
    ma10: indicators.ma10 ?? 0,
    ma20: indicators.ma20 ?? 0,
    ma60: indicators.ma60 ?? 0,
    volumeStatus: indicators.volumeStatus ?? '--',
    volumeRatio5d: indicators.volumeRatio5d ?? 0,
    macd: indicators.macd ?? EMPTY_MACD,
    rsi: indicators.rsi ?? EMPTY_RSI,
    ruleAssessment: detail.ruleAssessment ?? EMPTY_RULE,
    strategy: detail.strategy ?? EMPTY_STRATEGY,
    reasons: detail.reasons ?? [],
    riskFactors: detail.riskFactors ?? [],
    analysisMode: detail.analysisMode ?? 'fast',
    deepAnalysis: detail.deepAnalysis ?? null,
    generatedAt: detail.createdAt ?? '',
  };
};

const FundAdvicePage: React.FC = () => {
  const [fundCode, setFundCode] = useState('');
  const [days, setDays] = useState(120);
  const [mode, setMode] = useState<FundAdviceMode>('fast');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Current analysis view
  const [result, setResult] = useState<FundAdviceResponse | null>(null);
  
  // Tasks state
  const [tasks, setTasks] = useState<FundTaskInfo[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  
  // History state
  const [historyItems, setHistoryItems] = useState<FundHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerResult, setDrawerResult] = useState<FundAdviceResponse | null>(null);

  const pollIntervalRef = useRef<number | null>(null);

  const fetchTasks = async (silent = true) => {
    if (!silent) setTasksLoading(true);
    try {
      const res = await fundsApi.getTaskList(10);
      setTasks(res.tasks || []);
      
      // If no processing tasks, we can stop polling
      const hasProcessing = (res.tasks || []).some(t => t.status === 'processing');
      if (!hasProcessing && pollIntervalRef.current !== null) {
        window.clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        // Refresh history since a task might have finished
        fetchHistory(true);
      } else if (hasProcessing && pollIntervalRef.current === null) {
        // Start polling if not already started
        startPolling();
      }
    } catch (err) {
      console.warn('Failed to fetch tasks', err);
    } finally {
      if (!silent) setTasksLoading(false);
    }
  };

  const fetchHistory = async (silent = true) => {
    if (!silent) setHistoryLoading(true);
    try {
      const res = await fundsApi.getHistoryList({ limit: 12 });
      setHistoryItems(res.items || []);
    } catch (err) {
      console.warn('Failed to fetch history', err);
    } finally {
      if (!silent) setHistoryLoading(false);
    }
  };

  const startPolling = () => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
    }
    pollIntervalRef.current = window.setInterval(() => {
      fetchTasks(true);
    }, 5000);
  };

  useEffect(() => {
    fetchTasks(false);
    fetchHistory(false);
    return () => {
      if (pollIntervalRef.current !== null) {
        window.clearInterval(pollIntervalRef.current);
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAnalyze = async () => {
    const validation = validateFundCode(fundCode);
    if (!validation.valid) {
      setError(validation.message || '基金代码无效');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      if (mode === 'fast') {
        const data = await fundsApi.getAdvice(validation.normalized, days, mode);
        setResult(data);
        fetchHistory(true);
      } else {
        await fundsApi.analyze(validation.normalized, days, mode, true);
        fetchTasks(true);
        startPolling();
        setFundCode('');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '分析失败';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFundCode('');
    setError(null);
    setResult(null);
  };

  const handleExample = (code: string) => {
    setFundCode(code);
    setError(null);
  };

  const handleHistorySelect = async (item: FundHistoryItem) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDrawerResult(null);
    try {
      const data = await fundsApi.getHistoryDetail(item.id);
      if (data) {
        setDrawerResult(mapHistoryDetailToAdvice(data));
      }
    } catch (err) {
      console.warn('获取基金历史详情失败', err);
    } finally {
      setDrawerLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-warm-bg text-charcoal font-sans selection:bg-clay/20 selection:text-charcoal flex flex-col pt-6 md:pt-10">
      
      {/* Header & Toolbar Area */}
      <div className="max-w-[1400px] w-full mx-auto px-4 md:px-8 mb-6 shrink-0">
        <header className="mb-6">
          <h1 className="text-2xl md:text-3xl font-serif text-charcoal mb-2 tracking-tight">基金分析工作台</h1>
          <p className="text-sm text-charcoal-muted max-w-xl">
            用更温和、清晰的方式查看基金分析结果、异步任务进度与历史归档。
          </p>
        </header>

        <Toolbar
          fundCode={fundCode}
          setFundCode={setFundCode}
          days={days}
          setDays={setDays}
          mode={mode}
          setMode={setMode}
          loading={loading}
          onAnalyze={handleAnalyze}
          onClear={handleClear}
          onExample={handleExample}
        />

        {error && (
          <div className="mt-4 bg-red-50/80 border border-red-200 text-red-700 px-5 py-3 rounded-xl text-sm animate-fade-in shadow-sm flex items-start gap-3">
            <svg className="w-5 h-5 shrink-0 mt-0.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="font-medium">分析失败</p>
              <p className="opacity-90 mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Main Workspace Area */}
      <div className="max-w-[1400px] w-full mx-auto px-4 md:px-8 flex flex-col lg:flex-row gap-6 lg:gap-8 pb-12 flex-1 min-h-0">
        
        {/* Left Column (Main Content) - Approx 2/3 width */}
        <div className="flex-1 min-w-0 flex flex-col gap-6">
          {/* Default Empty State */}
          {!result && !loading && tasks.length === 0 && (
            <div className="flex-1 min-h-[400px] rounded-2xl border border-dashed border-warm-border/60 bg-warm-surface/30 flex flex-col items-center justify-center p-8 text-center animate-fade-in">
              <div className="w-16 h-16 mb-4 rounded-full bg-warm-surface flex items-center justify-center border border-warm-border/50">
                <svg className="w-8 h-8 text-charcoal/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <h3 className="text-base font-medium text-charcoal mb-1">准备开始分析</h3>
              <p className="text-sm text-charcoal-muted max-w-sm">
                在上方输入基金代码，并选择快速或深度模式，即可开始查看分析结论。
              </p>
            </div>
          )}

          {/* Current Result */}
          {result && !loading && (
             <div className="animate-slide-up">
               <h3 className="text-xs font-semibold tracking-wider uppercase text-charcoal-muted mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-clay"></span>
                  当前分析
               </h3>
               <HeroSummary result={result} />
             </div>
          )}
          
          {/* Active Tasks */}
          <div className={`transition-all duration-500 ${tasks.length > 0 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 hidden'}`}>
             <h3 className="text-xs font-semibold tracking-wider uppercase text-charcoal-muted mb-3 flex items-center gap-2">
                <svg className="w-3.5 h-3.5 animate-spin-slow" fill="none" viewBox="0 0 24 24">
                   <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"></circle>
                   <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                异步任务
             </h3>
             <AsyncTaskIndicator 
               tasks={tasks} 
               loading={tasksLoading} 
               onRefresh={() => fetchTasks(false)} 
             />
          </div>
        </div>

        {/* Right Column (History Rail) - Approx 1/3 width */}
        <div className="w-full lg:w-80 xl:w-96 shrink-0 flex flex-col gap-3">
          <h3 className="text-xs font-semibold tracking-wider uppercase text-charcoal-muted flex items-center justify-between">
            <span>历史归档</span>
            {historyLoading && <span className="text-[10px] text-clay/70 tracking-normal bg-clay/5 px-2 py-0.5 rounded-full">同步中...</span>}
          </h3>
          <div className="bg-warm-surface rounded-2xl border border-warm-border p-2">
             <HistoryList 
               items={historyItems} 
               loading={historyLoading} 
               onSelect={handleHistorySelect} 
               onRefresh={() => fetchHistory(false)} 
             />
          </div>
        </div>

      </div>

      {/* Detail Drawer Side Panel */}
      <DetailDrawer 
        open={drawerOpen} 
        onClose={() => setDrawerOpen(false)} 
        result={drawerResult} 
        loading={drawerLoading} 
      />
    </div>
  );
};

export default FundAdvicePage;
