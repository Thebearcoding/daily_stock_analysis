import React from 'react';
import type { FundAdviceResponse } from '../../types/funds';
import { HeroSummary } from './HeroSummary';

// A placeholder detail viewer to share state / types
interface DetailDrawerProps {
  open: boolean;
  onClose: () => void;
  result: FundAdviceResponse | null;
  loading: boolean;
}

const fmt = (value: unknown, digits = 4): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  return num.toFixed(digits);
};

export const DetailDrawer: React.FC<DetailDrawerProps> = ({
  open,
  onClose,
  result,
  loading,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/20 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Drawer panel */}
      <div className="relative w-full max-w-3xl bg-warm-bg h-full shadow-2xl flex flex-col animate-slide-in-right overflow-hidden overflow-y-auto">
        <header className="sticky top-0 bg-warm-bg/90 backdrop-blur-md border-b border-warm-border p-4 flex justify-between items-center z-10 px-6">
          <h2 className="text-xl font-serif text-charcoal font-medium">分析详情</h2>
          <button 
            type="button" 
            onClick={onClose}
            className="text-charcoal-muted hover:text-charcoal transition-colors px-3 py-1 rounded bg-warm-surface-alt border border-warm-border"
          >
            关闭
          </button>
        </header>

        <div className="p-6 flex flex-col gap-6">
          {loading ? (
            <div className="py-20 text-center text-charcoal flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-clay/20 border-t-clay rounded-full animate-spin" />
              <p>正在加载历史详情...</p>
            </div>
          ) : !result ? (
            <div className="py-20 text-center text-charcoal-muted">暂无可展示的详情。</div>
          ) : (
            <>
              {/* Summary overview */}
              <HeroSummary result={result} />

              {/* Advanced Indicators */}
              <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <article className="glass-panel rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-charcoal mb-3 uppercase tracking-wider">MACD / RSI 指标</h3>
                  <div className="flex justify-between items-center text-xs text-charcoal-muted border-b border-warm-border/50 pb-2">
                    <span>DIF {fmt(result.macd?.dif)}</span>
                    <span>DEA {fmt(result.macd?.dea)}</span>
                    <span>BAR {fmt(result.macd?.bar)}</span>
                  </div>
                  <p className="text-sm text-charcoal mt-3">{result.macd?.status || '--'}</p>
                  <p className="text-xs text-charcoal-muted mt-1">{result.macd?.signal || '--'}</p>
                  
                  <div className="flex justify-between items-center text-xs text-charcoal-muted border-b border-warm-border/50 pb-2 mt-4">
                    <span>RSI6 {fmt(result.rsi?.rsi6, 1)}</span>
                    <span>RSI12 {fmt(result.rsi?.rsi12, 1)}</span>
                    <span>RSI24 {fmt(result.rsi?.rsi24, 1)}</span>
                  </div>
                  <p className="text-sm text-charcoal mt-3">{result.rsi?.status || '--'}</p>
                  <p className="text-xs text-charcoal-muted mt-1">{result.rsi?.signal || '--'}</p>
                </article>

                <article className="glass-panel rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-charcoal mb-3 uppercase tracking-wider">规则判断</h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex flex-col gap-1 border-b border-warm-border/50 pb-2">
                      <p className="text-charcoal">{result.ruleAssessment?.entryRule || '入场规则'}</p>
                      <span className={result.ruleAssessment?.entryReady ? 'text-clay font-medium' : 'text-charcoal-muted'}>
                        {result.ruleAssessment?.entryReady ? '已满足' : '未满足'}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-charcoal">{result.ruleAssessment?.exitRule || '离场规则'}</p>
                      <span className={result.ruleAssessment?.exitTriggered ? 'text-charcoal font-medium' : 'text-charcoal-muted'}>
                        {result.ruleAssessment?.exitTriggered ? '已触发' : '未触发'}
                      </span>
                    </div>
                  </div>
                  <div className="mt-4 p-3 bg-warm-surface-alt rounded border border-warm-border/50">
                    <p className="text-xs text-charcoal-muted leading-relaxed">
                      {result.ruleAssessment?.comment || '当前暂无额外说明。'}
                    </p>
                  </div>
                </article>
              </section>

              {/* Strategy Positions */}
              <section className="glass-panel rounded-xl p-5">
                <h3 className="text-sm font-semibold text-charcoal mb-4 uppercase tracking-wider">策略建议</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-sm">
                  <div>
                    <p className="text-xs text-charcoal-muted uppercase mb-1">建议买入区间</p>
                    <p className="font-serif text-charcoal font-medium text-lg">
                      {fmt(result.strategy?.buyZone?.low)} - {fmt(result.strategy?.buyZone?.high)}
                    </p>
                    <p className="text-xs text-charcoal-muted mt-1">{result.strategy?.buyZone?.description || '--'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-charcoal-muted uppercase mb-1">建议加仓区间</p>
                    <p className="font-serif text-charcoal font-medium text-lg">
                      {fmt(result.strategy?.addZone?.low)} - {fmt(result.strategy?.addZone?.high)}
                    </p>
                    <p className="text-xs text-charcoal-muted mt-1">{result.strategy?.addZone?.description || '--'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-charcoal-muted uppercase mb-1">止损 / 止盈</p>
                    <p className="font-serif text-charcoal font-medium text-lg">
                      {fmt(result.strategy?.stopLoss)} / {fmt(result.strategy?.takeProfit)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-charcoal-muted uppercase mb-1">仓位建议</p>
                    <p className="font-medium text-charcoal text-lg">{result.strategy?.positionAdvice || '--'}</p>
                  </div>
                </div>
              </section>

              {/* Reasons & Risks */}
              <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <article className="glass-panel rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-charcoal mb-3 uppercase tracking-wider">支持因素</h3>
                  {result.reasons && result.reasons.length > 0 ? (
                    <ul className="space-y-2 text-sm text-charcoal-muted list-disc pl-4 marker:text-clay">
                      {result.reasons.map((item, idx) => <li key={`r-${idx}`}>{item}</li>)}
                    </ul>
                  ) : <p className="text-sm text-charcoal-muted">暂无补充说明。</p>}
                </article>

                <article className="glass-panel rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-charcoal mb-3 uppercase tracking-wider">风险提示</h3>
                  {result.riskFactors && result.riskFactors.length > 0 ? (
                    <ul className="space-y-2 text-sm text-charcoal-muted list-disc pl-4 marker:text-charcoal-muted">
                      {result.riskFactors.map((item, idx) => <li key={`risk-${idx}`}>{item}</li>)}
                    </ul>
                  ) : <p className="text-sm text-charcoal-muted">暂无风险提示。</p>}
                </article>
              </section>

              {/* Deep Analysis */}
              {result.analysisMode === 'deep' && (
                <section className="glass-panel rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-charcoal mb-4 uppercase tracking-wider">深度分析</h3>
                  {result.deepAnalysis?.status === 'completed' ? (
                    <div className="space-y-5">
                      <p className="text-charcoal text-sm leading-relaxed bg-warm-surface-alt p-4 rounded-lg border border-warm-border/50">
                        {result.deepAnalysis.summary?.analysisSummary || '深度分析已完成，但暂无摘要内容。'}
                      </p>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4">
                        <div>
                          <p className="text-xs text-charcoal-muted uppercase mb-1">操作建议与趋势</p>
                          <p className="text-charcoal text-sm font-medium">
                            {result.deepAnalysis.summary?.operationAdvice || '--'} / {result.deepAnalysis.summary?.trendPrediction || '--'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-charcoal-muted uppercase mb-1">情绪与倾向</p>
                          <p className="text-charcoal text-sm font-medium">
                            {result.deepAnalysis.summary?.sentimentScore ?? '--'} {result.deepAnalysis.summary?.sentimentLabel || ''}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-charcoal-muted uppercase mb-1">深度策略买点</p>
                          <p className="text-charcoal text-sm font-medium">
                            理想 {fmt(result.deepAnalysis.strategy?.idealBuy)} / 次级 {fmt(result.deepAnalysis.strategy?.secondaryBuy)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-charcoal-muted uppercase mb-1">深度策略退出</p>
                          <p className="text-charcoal text-sm font-medium">
                            止损 {fmt(result.deepAnalysis.strategy?.stopLoss)} / 止盈 {fmt(result.deepAnalysis.strategy?.takeProfit)}
                          </p>
                        </div>
                      </div>

                      {result.deepAnalysis.details?.newsSummary && (
                        <div className="border-t border-warm-border pt-4">
                          <p className="text-xs text-charcoal-muted uppercase mb-2">新闻上下文</p>
                          <p className="text-sm text-charcoal-muted leading-relaxed">
                            {result.deepAnalysis.details.newsSummary}
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-warm-border bg-warm-surface-alt px-4 py-3 text-sm text-charcoal-muted flex items-center gap-2">
                      <svg className="w-4 h-4 text-clay" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      深度分析数据暂不可用或尚未完整返回。
                      {result.deepAnalysis?.error && ` (${result.deepAnalysis.error})`}
                    </div>
                  )}
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
