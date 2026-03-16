import React from 'react';
import type { FundTaskInfo } from '../../types/funds';

interface AsyncTaskIndicatorProps {
  tasks: FundTaskInfo[];
  loading: boolean;
  onRefresh: () => void;
}

export const AsyncTaskIndicator: React.FC<AsyncTaskIndicatorProps> = ({
  tasks,
  loading,
  onRefresh,
}) => {
  if (tasks.length === 0) return null;

  const statusLabel = (status: string) => {
    switch (status) {
      case 'pending':
        return '等待中';
      case 'processing':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      default:
        return status;
    }
  };

  return (
    <section className="glass-panel rounded-2xl p-5 animate-fade-in">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-warm-border/50">
        <h3 className="text-sm font-semibold text-charcoal flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            {tasks.some(t => t.status === 'processing') && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-clay opacity-75"></span>
            )}
            <span className="relative inline-flex rounded-full h-2 w-2 bg-clay"></span>
          </span>
          异步任务（{tasks.length}）
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="text-xs text-charcoal-muted hover:text-charcoal transition-colors disabled:opacity-50"
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </div>

      <div className="space-y-3">
        {tasks.map((task) => (
          <div
            key={task.taskId}
            className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 bg-warm-bg rounded-xl border border-warm-border/50 transition-colors hover:border-warm-border"
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-charcoal">
                  {task.fundName || task.fundCode}
                </span>
                <span className="text-xs text-charcoal-muted font-mono bg-warm-surface px-1.5 py-0.5 rounded">
                  {task.fundCode}
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
                  task.status === 'processing' ? 'bg-clay/10 text-clay border-clay/20' :
                  task.status === 'completed' ? 'bg-charcoal/5 text-charcoal-muted border-charcoal/10' :
                  task.status === 'failed' ? 'text-red-700 bg-red-50 border-red-200' :
                  'bg-warm-surface-alt text-charcoal-muted border-warm-border'
                }`}>
                  {statusLabel(task.status)}
                </span>
              </div>
              <p className="text-xs text-charcoal-muted truncate max-w-md">
                {task.message || '后台正在处理本次分析，请稍候。'}
              </p>
              {task.error && (
                <p className="text-xs text-red-600 mt-1 truncate max-w-md" title={task.error}>
                  错误：{task.error}
                </p>
              )}
            </div>

            <div className="flex flex-col items-end gap-1 min-w-[100px]">
              <div className="flex items-center justify-between w-full text-xs text-charcoal-muted">
                <span>进度</span>
                <span className="font-mono">{task.progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-warm-border/50 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    task.status === 'failed' ? 'bg-red-400' : 'bg-clay'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, task.progress))}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
