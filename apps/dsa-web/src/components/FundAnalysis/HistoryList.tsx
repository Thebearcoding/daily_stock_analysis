import React from 'react';
import type { FundHistoryItem } from '../../types/funds';

interface HistoryListProps {
  items: FundHistoryItem[];
  loading: boolean;
  onSelect: (item: FundHistoryItem) => void;
  onRefresh: () => void;
}

const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d);
};

export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  loading,
  onSelect,
  onRefresh,
}) => {
  return (
    <section className="glass-panel rounded-2xl p-6 flex flex-col gap-4 animate-fade-in">
      <div className="flex items-center justify-between border-b border-warm-border/50 pb-2">
        <h3 className="text-lg font-serif text-charcoal font-medium">最近记录</h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="text-xs text-charcoal-muted hover:text-charcoal transition-colors disabled:opacity-50 underline decoration-warm-border underline-offset-4"
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-6 text-charcoal-muted text-sm border border-dashed border-warm-border rounded-xl">
          暂无基金分析记录。
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect(item)}
              type="button"
              className="text-left bg-warm-bg border border-warm-border/60 hover:border-clay hover:shadow-sm rounded-xl p-4 transition-all group flex flex-col gap-2 relative overflow-hidden"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="font-medium text-charcoal group-hover:text-clay transition-colors">
                    {item.fundName || item.analysisName || item.fundCode}
                  </h4>
                  <p className="text-xs text-charcoal-muted bg-warm-surface-alt px-1.5 py-0.5 rounded inline-block mt-1">
                    {item.fundCode}
                  </p>
                </div>
                {item.action && (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
                    item.action.toLowerCase() === 'buy' ? 'bg-clay/10 text-clay border-clay/20' :
                    item.action.toLowerCase() === 'reduce' ? 'bg-charcoal/5 text-charcoal-muted border-charcoal/10' :
                    'bg-warm-surface-alt text-charcoal border-warm-border'
                  }`}>
                    {item.action}
                  </span>
                )}
              </div>

              <div className="flex justify-between items-center text-xs text-charcoal-muted mt-2">
                <span>{item.analysisMode === 'deep' ? '深度分析' : '快速分析'}</span>
                <span>{formatDate(item.createdAt)}</span>
              </div>

              <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-clay/5 rounded-full blur-xl group-hover:bg-clay/10 transition-colors pointer-events-none" />
            </button>
          ))}
        </div>
      )}
    </section>
  );
};
