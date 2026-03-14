import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import type { HistoryItem, AnalysisReport, TaskInfo } from '../types/analysis';
import { historyApi } from '../api/history';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { validateStockCode } from '../utils/validation';
import { getRecentStartDate, toDateInputValue } from '../utils/format';
import { useAnalysisStore } from '../stores/analysisStore';
import { ReportSummary } from '../components/report';
import { HistoryList } from '../components/history';
import { TaskPanel } from '../components/tasks';
import { useTaskStream } from '../hooks';

/**
 * 首页 - 单页设计
 * 顶部输入 + 左侧历史 + 右侧报告
 */
const HomePage: React.FC = () => {
  const {
    setLoading,
    setError: setStoreError,
    error: storeError,
  } = useAnalysisStore();

  // 输入状态
  const [stockCode, setStockCode] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputError, setInputError] = useState<string>();

// 历史列表状态
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // 报告详情状态
  const [selectedReport, setSelectedReport] = useState<AnalysisReport | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  // 任务队列状态
  const [activeTasks, setActiveTasks] = useState<TaskInfo[]>([]);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  // 用于跟踪当前分析请求，避免竞态条件
  const analysisRequestIdRef = useRef<number>(0);

  // 更新任务列表中的任务
  const updateTask = useCallback((updatedTask: TaskInfo) => {
    setActiveTasks((prev) => {
      const index = prev.findIndex((t) => t.taskId === updatedTask.taskId);
      if (index >= 0) {
        const newTasks = [...prev];
        newTasks[index] = updatedTask;
        return newTasks;
      }
      return prev;
    });
  }, []);

  // 移除已完成/失败的任务
  const removeTask = useCallback((taskId: string) => {
    setActiveTasks((prev) => prev.filter((t) => t.taskId !== taskId));
  }, []);

  // SSE 任务流
  useTaskStream({
    onTaskCreated: (task) => {
      setActiveTasks((prev) => {
        // 避免重复添加
        if (prev.some((t) => t.taskId === task.taskId)) return prev;
        return [...prev, task];
      });
    },
    onTaskStarted: updateTask,
    onTaskCompleted: (task) => {
      // 刷新历史列表
      fetchHistory();
      // 延迟移除任务，让用户看到完成状态
      setTimeout(() => removeTask(task.taskId), 2000);
    },
    onTaskFailed: (task) => {
      updateTask(task);
      // 显示错误提示
      setStoreError(task.error || '分析失败');
      // 延迟移除任务
      setTimeout(() => removeTask(task.taskId), 5000);
    },
    onError: () => {
      console.warn('SSE 连接断开，正在重连...');
    },
    enabled: true,
  });

// 加载历史列表
  const fetchHistory = useCallback(async (autoSelectFirst = false, reset = true) => {
    if (reset) {
      setIsLoadingHistory(true);
      setCurrentPage(1);
    } else {
      setIsLoadingMore(true);
    }

    const page = reset ? 1 : currentPage + 1;

    try {
      const response = await historyApi.getList({
        startDate: getRecentStartDate(30),
        endDate: toDateInputValue(new Date()),
        page,
        limit: pageSize,
      });

      if (reset) {
        setHistoryItems(response.items);
      } else {
        setHistoryItems(prev => [...prev, ...response.items]);
      }

      // 判断是否还有更多数据
      const totalLoaded = reset ? response.items.length : historyItems.length + response.items.length;
      setHasMore(totalLoaded < response.total);
      setCurrentPage(page);

      // 如果需要自动选择第一条，且有数据，且当前没有选中报告
      if (autoSelectFirst && response.items.length > 0 && !selectedReport) {
        const firstItem = response.items[0];
        setSelectedId(firstItem.id);
        setIsLoadingReport(true);
        try {
          const report = await historyApi.getDetailById(firstItem.id);
          setSelectedReport(report);
        } catch (err) {
          console.error('Failed to fetch first report:', err);
        } finally {
          setIsLoadingReport(false);
        }
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setIsLoadingHistory(false);
      setIsLoadingMore(false);
    }
  }, [selectedReport, currentPage, historyItems.length, pageSize]);

  // 加载更多历史记录
  const handleLoadMore = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      fetchHistory(false, false);
    }
  }, [fetchHistory, isLoadingMore, hasMore]);

  // 初始加载 - 自动选择第一条
  useEffect(() => {
    fetchHistory(true);
  }, []);

  // 点击历史项加载报告
  const handleHistoryClick = async (id: string, _queryId: string) => {
    // 取消当前分析请求的结果显示（通过递增 requestId）
    analysisRequestIdRef.current += 1;

    setSelectedId(id);
    setIsLoadingReport(true);
    try {
      const report = await historyApi.getDetailById(id);
      setSelectedReport(report);
    } catch (err) {
      console.error('Failed to fetch report:', err);
    } finally {
      setIsLoadingReport(false);
    }
  };

  // 删除历史记录
  const handleDelete = async (id: string) => {
    if (!window.confirm('确定要删除这条记录吗？')) {
      return;
    }

    try {
      await historyApi.deleteById(id);
      // 从列表中移除
      setHistoryItems(prev => prev.filter(item => item.id !== id));
      // 如果删除的是当前选中的，清空选中状态
      if (selectedId === id) {
        setSelectedId(null);
        setSelectedReport(null);
      }
    } catch (err) {
      console.error('Failed to delete:', err);
      setStoreError('删除失败');
    }
  };

  // 分析股票（异步模式）
  const handleAnalyze = async () => {
    const { valid, message, normalized } = validateStockCode(stockCode);
    if (!valid) {
      setInputError(message);
      return;
    }

    setInputError(undefined);
    setDuplicateError(null);
    setIsAnalyzing(true);
    setLoading(true);
    setStoreError(null);

    // 记录当前请求的 ID
    const currentRequestId = ++analysisRequestIdRef.current;

    try {
      // 使用异步模式提交分析
      const response = await analysisApi.analyzeAsync({
        stockCode: normalized,
        reportType: 'detailed',
      });

      // 清空输入框
      if (currentRequestId === analysisRequestIdRef.current) {
        setStockCode('');
      }

      // 任务已提交，SSE 会推送更新
      console.log('Task submitted:', response.taskId);
    } catch (err) {
      console.error('Analysis failed:', err);
      if (currentRequestId === analysisRequestIdRef.current) {
        if (err instanceof DuplicateTaskError) {
          // 显示重复任务错误
          setDuplicateError(`股票 ${err.stockCode} 正在分析中，请等待完成`);
        } else {
          setStoreError(err instanceof Error ? err.message : '分析失败');
        }
      }
    } finally {
      setIsAnalyzing(false);
      setLoading(false);
    }
  };

  // 回车提交
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && stockCode && !isAnalyzing) {
      handleAnalyze();
    }
  };

  return (
    <div className="px-4 py-4 md:px-6 md:py-5 space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-5 shadow-sm">
        <div className="flex flex-col gap-3">
          <div>
            <h1 className="text-lg md:text-xl font-semibold text-slate-900">股票分析工作台</h1>
            <p className="text-sm text-slate-600 mt-1">
              输入股票代码后提交分析任务，左侧查看任务和历史，右侧查看报告详情。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[220px]">
              <input
                type="text"
                value={stockCode}
                onChange={(e) => {
                  setStockCode(e.target.value.toUpperCase());
                  setInputError(undefined);
                }}
                onKeyDown={handleKeyDown}
                placeholder="输入股票代码，如 600519、00700、AAPL"
                disabled={isAnalyzing}
                className={`input-terminal w-full ${inputError ? 'border-danger/50' : ''}`}
              />
              {inputError && (
                <p className="absolute -bottom-5 left-0 text-xs text-danger">{inputError}</p>
              )}
              {duplicateError && (
                <p className="absolute -bottom-5 left-0 text-xs text-warning">{duplicateError}</p>
              )}
            </div>

            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!stockCode || isAnalyzing}
              className="btn-primary flex items-center gap-1.5 whitespace-nowrap"
            >
              {isAnalyzing ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  提交中
                </>
              ) : (
                '提交分析'
              )}
            </button>
          </div>
        </div>
      </section>

      {storeError && (
        <section className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {storeError}
        </section>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-[320px_minmax(0,1fr)] gap-4 items-start">
        <aside className="space-y-3">
          <TaskPanel tasks={activeTasks} />

          <HistoryList
            items={historyItems}
            isLoading={isLoadingHistory}
            isLoadingMore={isLoadingMore}
            hasMore={hasMore}
            selectedId={selectedId || undefined}
            onItemClick={handleHistoryClick}
            onDelete={handleDelete}
            onLoadMore={handleLoadMore}
            className="max-h-[64vh] overflow-hidden"
          />
        </aside>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-h-[64vh]">
          {isLoadingReport ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[420px]">
              <div className="w-10 h-10 border-3 border-cyan/20 border-t-cyan rounded-full animate-spin" />
              <p className="mt-3 text-secondary text-sm">加载报告中...</p>
            </div>
          ) : selectedReport ? (
            <div className="max-w-4xl mx-auto">
              <ReportSummary data={selectedReport} isHistory />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full min-h-[420px] text-center">
              <div className="w-12 h-12 mb-3 rounded-xl bg-slate-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="text-base font-medium text-slate-900 mb-1.5">等待分析结果</h3>
              <p className="text-sm text-slate-600 max-w-sm">
                提交一个股票代码，或从左侧历史中选择报告查看。
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default HomePage;
