import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Badge, Pagination } from '../components/common';
import type {
  BacktestResultItem,
  BacktestRunResponse,
  PerformanceMetrics,
} from '../types/backtest';

// ============ Helpers ============

function pct(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

function outcomeBadge(outcome?: string) {
  if (!outcome) return <Badge variant="default">--</Badge>;
  switch (outcome) {
    case 'win':
      return <Badge variant="success" glow>盈利</Badge>;
    case 'loss':
      return <Badge variant="danger" glow>亏损</Badge>;
    case 'neutral':
      return <Badge variant="warning">持平</Badge>;
    default:
      return <Badge variant="default">{outcome}</Badge>;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success">已完成</Badge>;
    case 'insufficient':
      return <Badge variant="warning">样本不足</Badge>;
    case 'error':
      return <Badge variant="danger">异常</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
}

function boolIcon(value?: boolean | null) {
  if (value === true) return <span className="text-emerald-400">&#10003;</span>;
  if (value === false) return <span className="text-red-400">&#10007;</span>;
  return <span className="text-muted">--</span>;
}

function directionLabel(direction?: string) {
  if (!direction) return '--';
  switch (direction.toLowerCase()) {
    case 'up':
    case 'bullish':
    case 'long':
      return '看多';
    case 'down':
    case 'bearish':
    case 'short':
      return '看空';
    case 'neutral':
    case 'flat':
    case 'cash':
      return '中性';
    default:
      return direction;
  }
}

// ============ Metric Row ============

const MetricRow: React.FC<{ label: string; value: string; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-warm-border/50 last:border-0">
    <span className="text-xs text-charcoal-muted">{label}</span>
    <span className={`text-sm font-mono font-semibold ${accent ? 'text-clay' : 'text-charcoal'}`}>{value}</span>
  </div>
);

// ============ Performance Card ============

const PerformanceCard: React.FC<{ metrics: PerformanceMetrics; title: string }> = ({ metrics, title }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in">
    <div className="mb-3">
      <span className="label-uppercase">{title}</span>
    </div>
    <MetricRow label="方向判断准确率" value={pct(metrics.directionAccuracyPct)} accent />
    <MetricRow label="盈利占比" value={pct(metrics.winRatePct)} accent />
    <MetricRow label="模拟收益均值" value={pct(metrics.avgSimulatedReturnPct)} />
    <MetricRow label="标的收益均值" value={pct(metrics.avgStockReturnPct)} />
    <MetricRow label="止损触发率" value={pct(metrics.stopLossTriggerRate)} />
    <MetricRow label="止盈触发率" value={pct(metrics.takeProfitTriggerRate)} />
    <MetricRow label="首次触发平均天数" value={metrics.avgDaysToFirstHit != null ? metrics.avgDaysToFirstHit.toFixed(1) : '--'} />
    <div className="mt-3 pt-2 border-t border-warm-border/50 flex items-center justify-between">
      <span className="text-xs text-charcoal-muted">已评估样本</span>
      <span className="text-xs text-charcoal font-mono">
        {Number(metrics.completedCount)} / {Number(metrics.totalEvaluations)}
      </span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-charcoal-muted">盈 / 亏 / 平</span>
      <span className="text-xs font-mono">
        <span className="text-emerald-600">{metrics.winCount}</span>
        {' / '}
        <span className="text-red-500">{metrics.lossCount}</span>
        {' / '}
        <span className="text-amber-500">{metrics.neutralCount}</span>
      </span>
    </div>
  </Card>
);

// ============ Run Summary ============

const RunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <div className="flex items-center gap-4 px-3 py-2 rounded-lg glass-panel text-xs font-mono animate-fade-in">
    <span className="text-charcoal-muted">处理总数: <span className="text-charcoal">{data.processed}</span></span>
    <span className="text-charcoal-muted">写入记录: <span className="text-clay">{data.saved}</span></span>
    <span className="text-charcoal-muted">完成评估: <span className="text-emerald-600">{data.completed}</span></span>
    <span className="text-charcoal-muted">样本不足: <span className="text-amber-500">{data.insufficient}</span></span>
    {data.errors > 0 && (
      <span className="text-charcoal-muted">错误数: <span className="text-red-500">{data.errors}</span></span>
    )}
  </div>
);

// ============ Main Page ============

const BacktestPage: React.FC = () => {
  // Input state
  const [codeFilter, setCodeFilter] = useState('');
  const [evalDays, setEvalDays] = useState('');
  const [forceRerun, setForceRerun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // Results state
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;

  // Performance state
  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);

  // Fetch results
  const fetchResults = useCallback(async (page = 1, code?: string, windowDays?: number) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({ code: code || undefined, evalWindowDays: windowDays, page, limit: pageSize });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch backtest results:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  // Fetch performance
  const fetchPerformance = useCallback(async (code?: string, windowDays?: number) => {
    setIsLoadingPerf(true);
    try {
      const overall = await backtestApi.getOverallPerformance(windowDays);
      setOverallPerf(overall);

      if (code) {
        const stock = await backtestApi.getStockPerformance(code, windowDays);
        setStockPerf(stock);
      } else {
        setStockPerf(null);
      }
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch performance:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, []);

  // Initial load — fetch performance first, then filter results by its window
  useEffect(() => {
    const init = async () => {
      // Get latest performance (unfiltered returns most recent summary)
      const overall = await backtestApi.getOverallPerformance();
      setOverallPerf(overall);
      // Use the summary's eval_window_days to filter results consistently
      const windowDays = overall?.evalWindowDays;
      if (windowDays && !evalDays) {
        setEvalDays(String(windowDays));
      }
      fetchResults(1, undefined, windowDays);
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run backtest
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const code = codeFilter.trim() || undefined;
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.run({
        code,
        force: forceRerun || undefined,
        minAgeDays: forceRerun ? 0 : undefined,
        evalWindowDays,
      });
      setRunResult(response);
      // Refresh data with same eval_window_days
      fetchResults(1, codeFilter.trim() || undefined, evalWindowDays);
      fetchPerformance(codeFilter.trim() || undefined, evalWindowDays);
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Filter by code
  const handleFilter = () => {
    const code = codeFilter.trim() || undefined;
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    setCurrentPage(1);
    fetchResults(1, code, windowDays);
    fetchPerformance(code, windowDays);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFilter();
    }
  };

  // Pagination
  const totalPages = Math.ceil(totalResults / pageSize);
  const handlePageChange = (page: number) => {
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    fetchResults(page, codeFilter.trim() || undefined, windowDays);
  };

  const activeWindow = evalDays || (overallPerf?.evalWindowDays ? String(overallPerf.evalWindowDays) : '');
  const filterLabel = codeFilter.trim() || '全部股票';

  return (
    <div className="min-h-screen bg-warm-bg text-charcoal font-sans selection:bg-clay/20 selection:text-charcoal flex flex-col pt-6 md:pt-10">
      <div className="max-w-[1400px] w-full mx-auto flex flex-col gap-6 px-4 py-0 md:px-6 lg:px-8">
        <header className="mb-2">
          <h1 className="text-2xl md:text-3xl font-serif text-charcoal mb-2 tracking-tight">回测工作台</h1>
          <p className="text-sm text-charcoal-muted max-w-xl">
            用固定观察窗口复盘历史分析建议，快速查看方向判断、模拟收益和止盈止损触发情况。
          </p>
        </header>
        <section className="glass-panel rounded-2xl p-5 md:p-6">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr),420px]">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2.5 text-xs">
                <Badge variant="default">当前筛选：{filterLabel}</Badge>
                <Badge variant="default">观察窗口：{activeWindow || '--'} 天</Badge>
                <Badge variant="default">每页结果：{pageSize} 条</Badge>
              </div>
              {runResult ? <RunSummary data={runResult} /> : null}
              {runError ? <ApiErrorAlert error={runError} /> : null}
            </div>

            <div className="rounded-[26px] border border-warm-border/60 bg-warm-bg/80 p-4 md:p-5">
              <div className="mb-4">
                <span className="label-uppercase">控制台</span>
                <h2 className="mt-2 font-serif text-xl text-charcoal">回测控制台</h2>
                <p className="mt-1 text-sm text-charcoal-muted">
                  支持按股票代码筛选，并指定回测观察窗口。
                </p>
              </div>
              <div className="grid gap-3">
                <label className="space-y-1.5">
                  <span className="text-xs font-medium text-charcoal-muted">股票代码</span>
                  <input
                    type="text"
                    value={codeFilter}
                    onChange={(e) => setCodeFilter(e.target.value.toUpperCase())}
                    onKeyDown={handleKeyDown}
                    placeholder="输入股票代码，留空则查看全部"
                    disabled={isRunning}
                    className="input-terminal w-full"
                  />
                </label>

                <div className="grid gap-3 sm:grid-cols-[120px,minmax(0,1fr)]">
                  <label className="space-y-1.5">
                    <span className="text-xs font-medium text-charcoal-muted">观察窗口</span>
                    <input
                      type="number"
                      min={1}
                      max={120}
                      value={evalDays}
                      onChange={(e) => setEvalDays(e.target.value)}
                      placeholder="10"
                      disabled={isRunning}
                      className="input-terminal w-full text-center text-sm"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => setForceRerun(!forceRerun)}
                    disabled={isRunning}
                    className={`
                      mt-auto flex min-h-[44px] items-center justify-center gap-2 rounded-xl border px-4 text-sm font-medium
                      transition-all duration-200
                      ${forceRerun
                        ? 'border-charcoal bg-charcoal text-warm-bg'
                        : 'border-warm-border bg-warm-surface text-charcoal-muted hover:border-charcoal/30 hover:text-charcoal'
                      }
                      disabled:cursor-not-allowed disabled:opacity-50
                    `}
                  >
                    <span
                      className={`
                        inline-block h-2 w-2 rounded-full transition-colors duration-200
                        ${forceRerun ? 'bg-warm-bg' : 'bg-warm-border'}
                      `}
                    />
                    强制重算
                  </button>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={handleFilter}
                    disabled={isLoadingResults || isRunning}
                    className="btn-secondary flex min-h-[44px] items-center justify-center gap-2 whitespace-nowrap"
                  >
                    应用筛选
                  </button>
                  <button
                    type="button"
                    onClick={handleRun}
                    disabled={isRunning}
                    className="btn-primary flex min-h-[44px] items-center justify-center gap-2 whitespace-nowrap"
                  >
                    {isRunning ? (
                      <>
                        <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        回测执行中...
                      </>
                    ) : (
                      '开始回测'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {pageError ? <ApiErrorAlert error={pageError} /> : null}

        <main className="grid gap-6 xl:grid-cols-[300px,minmax(0,1fr)]">
          <aside className="space-y-4">
            {isLoadingPerf ? (
              <Card padding="lg" className="min-h-[220px]">
                <div className="flex h-full items-center justify-center py-8">
                  <div className="h-8 w-8 rounded-full border-2 border-clay/20 border-t-clay animate-spin" />
                </div>
              </Card>
            ) : overallPerf ? (
              <PerformanceCard metrics={overallPerf} title="整体表现" />
            ) : (
              <Card padding="lg">
                <div className="space-y-2 text-center">
                  <h3 className="font-serif text-lg text-charcoal">还没有回测数据</h3>
                  <p className="text-sm leading-6 text-charcoal-muted">
                    先执行一次回测，再查看整体表现、命中率和模拟收益。
                  </p>
                </div>
              </Card>
            )}

            {stockPerf ? (
              <PerformanceCard metrics={stockPerf} title={`${stockPerf.code || codeFilter} 表现`} />
            ) : null}
          </aside>

          <section className="min-w-0">
            <Card padding="none" className="overflow-hidden">
              <div className="border-b border-warm-border/60 bg-warm-surface-alt/60 px-5 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <div>
                    <span className="label-uppercase">结果</span>
                    <h2 className="mt-2 font-serif text-2xl text-charcoal">历史结果</h2>
                    <p className="mt-1 text-sm text-charcoal-muted">
                      查看每条分析建议在回测窗口中的方向表现、模拟收益和状态。
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2.5 text-xs">
                    <Badge variant="default">当前页：{currentPage}/{Math.max(totalPages, 1)}</Badge>
                    <Badge variant="default">总记录：{totalResults}</Badge>
                    {activeWindow ? <Badge variant="default">窗口：{activeWindow} 天</Badge> : null}
                  </div>
                </div>
              </div>

              <div className="px-5 py-5">
                {isLoadingResults ? (
                  <div className="flex min-h-[320px] flex-col items-center justify-center">
                    <div className="h-10 w-10 rounded-full border-[3px] border-clay/20 border-t-clay animate-spin" />
                    <p className="mt-3 text-sm text-charcoal-muted">正在加载回测结果...</p>
                  </div>
                ) : results.length === 0 ? (
                  <div className="flex min-h-[320px] flex-col items-center justify-center text-center">
                    <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-warm-border bg-warm-bg">
                      <svg className="h-7 w-7 text-charcoal-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                    </div>
                    <h3 className="font-serif text-xl text-charcoal">暂无回测结果</h3>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-charcoal-muted">
                      先执行一次回测，系统会在这里展示历史建议的准确率、收益和止盈止损触发结果。
                    </p>
                  </div>
                ) : (
                  <div className="animate-fade-in space-y-4">
                    <div className="overflow-x-auto rounded-2xl border border-warm-border bg-warm-surface shadow-sm">
                      <table className="w-full min-w-[860px] text-sm">
                        <thead>
                          <tr className="border-b border-warm-border bg-warm-surface-alt text-left">
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">代码</th>
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">分析日期</th>
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">建议</th>
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">方向验证</th>
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">结果</th>
                            <th className="px-4 py-3 text-right text-xs font-medium tracking-wide text-charcoal-muted">模拟收益</th>
                            <th className="px-4 py-3 text-center text-xs font-medium tracking-wide text-charcoal-muted">止损</th>
                            <th className="px-4 py-3 text-center text-xs font-medium tracking-wide text-charcoal-muted">止盈</th>
                            <th className="px-4 py-3 text-xs font-medium tracking-wide text-charcoal-muted">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.map((row) => (
                            <tr
                              key={row.analysisHistoryId}
                              className="border-t border-warm-border/50 transition-colors hover:bg-warm-surface-alt/70"
                            >
                              <td className="px-4 py-3 text-xs font-medium text-charcoal">
                                <div className="font-mono">{row.code}</div>
                                <div className="mt-1 text-[11px] text-charcoal-muted">
                                  窗口 {row.evalWindowDays} 天
                                </div>
                              </td>
                              <td className="px-4 py-3 text-xs text-charcoal-muted">{row.analysisDate || '--'}</td>
                              <td className="max-w-[180px] px-4 py-3 text-xs text-charcoal" title={row.operationAdvice || ''}>
                                <div className="line-clamp-2">{row.operationAdvice || '--'}</div>
                              </td>
                              <td className="px-4 py-3 text-xs">
                                <span className="flex items-center gap-2">
                                  {boolIcon(row.directionCorrect)}
                                  <span className="text-charcoal-muted">{directionLabel(row.directionExpected)}</span>
                                </span>
                              </td>
                              <td className="px-4 py-3">{outcomeBadge(row.outcome)}</td>
                              <td className="px-4 py-3 text-right text-xs font-mono">
                                <span
                                  className={
                                    row.simulatedReturnPct != null
                                      ? row.simulatedReturnPct > 0
                                        ? 'font-medium text-emerald-600'
                                        : row.simulatedReturnPct < 0
                                          ? 'font-medium text-red-500'
                                          : 'text-charcoal-muted'
                                      : 'text-charcoal-muted'
                                  }
                                >
                                  {pct(row.simulatedReturnPct)}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">{boolIcon(row.hitStopLoss)}</td>
                              <td className="px-4 py-3 text-center">{boolIcon(row.hitTakeProfit)}</td>
                              <td className="px-4 py-3">{statusBadge(row.evalStatus)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <Pagination
                      currentPage={currentPage}
                      totalPages={totalPages}
                      onPageChange={handlePageChange}
                    />
                  </div>
                )}
              </div>
            </Card>
          </section>
        </main>
      </div>
    </div>
  );
};

export default BacktestPage;
