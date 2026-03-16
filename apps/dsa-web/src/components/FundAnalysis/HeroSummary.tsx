import React from 'react';
import type { FundAdviceResponse } from '../../types/funds';

interface HeroSummaryProps {
  result: FundAdviceResponse;
}

const ACTION_STYLE: Record<string, string> = {
  buy: 'bg-clay/10 text-clay border-clay/20',
  hold: 'bg-warm-surface-alt text-charcoal border-warm-border',
  wait: 'bg-warm-surface-alt text-charcoal-muted border-warm-border',
  reduce: 'bg-charcoal/5 text-charcoal-muted border-charcoal/10',
};

const CONFIDENCE_STYLE: Record<string, string> = {
  高: 'text-clay font-medium',
  中: 'text-charcoal-muted',
  低: 'text-charcoal-muted',
};

const fmt = (value: unknown, digits = 4): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  return num.toFixed(digits);
};

export const HeroSummary: React.FC<HeroSummaryProps> = ({ result }) => {
  const actionClassName = ACTION_STYLE[result.action] || 'glass-panel text-charcoal';
  const confidenceClassName = CONFIDENCE_STYLE[result.confidenceLevel] || 'text-charcoal-muted';

  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      <section className="glass-panel rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-serif text-charcoal font-medium">
            {result.fundName || result.fundCode}
          </h2>
          <div className="flex flex-wrap items-center gap-2 mt-2 text-sm text-charcoal-muted">
            <span className="font-mono bg-warm-bg px-2 py-0.5 rounded border border-warm-border/50">{result.fundCode}</span>
            <span>·</span>
            <span>分析标的 {result.analysisCode}</span>
            {result.mappingNote && (
              <>
                <span>·</span>
                <span className="text-clay/80">{result.mappingNote}</span>
              </>
            )}
            <span>·</span>
            <span>{result.analysisMode === 'deep' ? '深度分析' : '快速分析'}</span>
            <span>·</span>
            <span>{result.latestDate}</span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="text-sm text-charcoal-muted block mb-0.5">当前结论</span>
              <span className={`inline-flex items-center px-4 py-1.5 rounded-full border text-sm shadow-sm ${actionClassName}`}>
                {result.actionLabel}
              </span>
            </div>
          </div>
          <div className="text-sm">
            <span className="text-charcoal-muted mr-1">置信度：</span>
            <span className={confidenceClassName}>{result.confidenceLevel} ({result.confidenceScore})</span>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel rounded-xl p-5">
          <p className="text-xs text-charcoal-muted uppercase tracking-wider mb-1">当前价格</p>
          <p className="text-2xl font-serif text-charcoal">{fmt(result.currentPrice)}</p>
          <div className="mt-3 text-xs text-charcoal-muted flex justify-between border-t border-warm-border/50 pt-2">
            <span>MA5 {fmt(result.ma5)}</span>
            <span>MA10 {fmt(result.ma10)}</span>
            <span>MA20 {fmt(result.ma20)}</span>
          </div>
        </div>

        <div className="glass-panel rounded-xl p-5">
          <p className="text-xs text-charcoal-muted uppercase tracking-wider mb-1">趋势与评分</p>
          <p className="text-lg font-medium text-charcoal">{result.trendStatus}</p>
          <div className="mt-4 text-xs text-charcoal-muted flex justify-between border-t border-warm-border/50 pt-2">
            <span>信号：{result.buySignal}</span>
            <span className="font-medium text-charcoal">评分：{result.signalScore}</span>
          </div>
        </div>

        <div className="glass-panel rounded-xl p-5">
          <p className="text-xs text-charcoal-muted uppercase tracking-wider mb-1">量能状态</p>
          <p className="text-lg font-medium text-charcoal">{result.volumeStatus}</p>
          <div className="mt-4 text-xs text-charcoal-muted flex justify-between border-t border-warm-border/50 pt-2">
            <span>5 日量比</span>
            <span className="font-mono">{fmt(result.volumeRatio5d, 2)}</span>
          </div>
        </div>
      </section>
    </div>
  );
};
