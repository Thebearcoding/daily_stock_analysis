import React from 'react';
import type { FundAdviceMode } from '../../api/funds';

interface ToolbarProps {
  fundCode: string;
  setFundCode: (code: string) => void;
  days: number;
  setDays: (days: number) => void;
  mode: FundAdviceMode;
  setMode: (mode: FundAdviceMode) => void;
  loading: boolean;
  onAnalyze: () => void;
  onClear: () => void;
  onExample: (code: string) => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  fundCode,
  setFundCode,
  days,
  setDays,
  mode,
  setMode,
  loading,
  onAnalyze,
  onClear,
  onExample,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading && fundCode.trim()) {
      onAnalyze();
    }
  };

  return (
    <section className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-serif text-charcoal font-medium">基金分析</h1>
        <p className="text-sm text-charcoal-muted mt-1 font-light">
          用更克制、可读的方式查看基金策略结论、风险提示与异步分析进度。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <input
            type="text"
            value={fundCode}
            onChange={(e) => setFundCode(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入 6 位基金代码，例如 024195"
            disabled={loading}
            className="w-full bg-warm-bg border border-warm-border rounded-xl px-4 py-2.5 text-charcoal focus:outline-none focus:border-clay focus:ring-1 focus:ring-clay transition-all placeholder:text-warm-border/80"
          />
        </div>

        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          disabled={loading}
          className="bg-warm-bg border border-warm-border rounded-xl px-4 py-2.5 text-charcoal focus:outline-none focus:border-clay transition-all cursor-pointer"
        >
          <option value={90}>近 90 天</option>
          <option value={120}>近 120 天</option>
          <option value={180}>近 180 天</option>
          <option value={240}>近 240 天</option>
        </select>

        <div className="fund-mode-toggle">
          <button
            type="button"
            onClick={() => setMode('fast')}
            disabled={loading}
            className={`fund-mode-toggle__item${mode === 'fast' ? ' is-active' : ''}`}
          >
            快速
          </button>
          <button
            type="button"
            onClick={() => setMode('deep')}
            disabled={loading}
            className={`fund-mode-toggle__item${mode === 'deep' ? ' is-active' : ''}`}
          >
            深度
          </button>
        </div>

        <button
          type="button"
          onClick={onAnalyze}
          disabled={loading || !fundCode.trim()}
          className="fund-primary-button"
        >
          {loading ? '分析中...' : '开始分析'}
        </button>

        <button
          type="button"
          onClick={onClear}
          disabled={loading}
          className="fund-secondary-button"
        >
          清空
        </button>
      </div>

      <div className="flex items-center gap-2 text-xs text-charcoal-muted">
        <span>示例：</span>
        <button type="button" onClick={() => onExample('024195')} className="hover:text-clay transition-colors underline decoration-warm-border underline-offset-4">024195</button>
        <button type="button" onClick={() => onExample('017811')} className="hover:text-clay transition-colors underline decoration-warm-border underline-offset-4">017811</button>
        <button type="button" onClick={() => onExample('012414')} className="hover:text-clay transition-colors underline decoration-warm-border underline-offset-4">012414</button>
      </div>
    </section>
  );
};
