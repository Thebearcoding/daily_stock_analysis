import type React from 'react';
import { useMemo, useState } from 'react';
import { fundsApi } from '../api/funds';
import type { FundAdviceMode } from '../api/funds';
import type { FundAdviceResponse } from '../types/funds';

const ACTION_STYLE: Record<string, string> = {
  buy: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  hold: 'bg-sky-100 text-sky-700 border-sky-200',
  wait: 'bg-amber-100 text-amber-700 border-amber-200',
  reduce: 'bg-rose-100 text-rose-700 border-rose-200',
};

const CONFIDENCE_STYLE: Record<string, string> = {
  高: 'text-emerald-700',
  中: 'text-amber-700',
  低: 'text-rose-700',
};

const validateFundCode = (value: string): { valid: boolean; message?: string; normalized: string } => {
  const normalized = value.trim();
  if (!normalized) {
    return { valid: false, message: '请输入基金代码', normalized };
  }
  if (!/^\d{6}$/.test(normalized)) {
    return { valid: false, message: '基金代码需为 6 位数字', normalized };
  }
  return { valid: true, normalized };
};

const fmt = (value: unknown, digits = 4): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '--';
  return num.toFixed(digits);
};

const FundAdvicePage: React.FC = () => {
  const [fundCode, setFundCode] = useState('');
  const [days, setDays] = useState(120);
  const [mode, setMode] = useState<FundAdviceMode>('fast');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FundAdviceResponse | null>(null);

  const actionClassName = useMemo(() => {
    if (!result) return '';
    return ACTION_STYLE[result.action] ?? 'bg-slate-100 text-slate-700 border-slate-200';
  }, [result]);

  const confidenceClassName = useMemo(() => {
    if (!result) return 'text-slate-500';
    return CONFIDENCE_STYLE[result.confidenceLevel] ?? 'text-slate-500';
  }, [result]);
  const reasonItems = result && Array.isArray(result.reasons) ? result.reasons : [];
  const riskItems = result && Array.isArray(result.riskFactors) ? result.riskFactors : [];

  const fetchAdvice = async (): Promise<void> => {
    const validation = validateFundCode(fundCode);
    if (!validation.valid) {
      setError(validation.message || '基金代码格式错误');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await fundsApi.getAdvice(validation.normalized, days, mode);
      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : '获取基金建议失败';
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === 'Enter' && !loading) {
      void fetchAdvice();
    }
  };

  return (
    <div className="px-4 py-4 md:px-6 md:py-5 space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-5 shadow-sm">
        <div className="flex flex-col gap-3">
          <div>
            <h1 className="text-lg md:text-xl font-semibold text-slate-900">基金策略建议</h1>
            <p className="text-sm text-slate-600 mt-1">
              支持场外基金自动映射 ETF，结合均线、MACD、RSI 和规则判定输出可执行建议。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[220px]">
              <input
                type="text"
                value={fundCode}
                onChange={(e) => {
                  setFundCode(e.target.value);
                  setError(null);
                }}
                onKeyDown={handleKeyDown}
                placeholder="输入基金代码，如 024195"
                className="input-terminal w-full"
                disabled={loading}
              />
              {error && (
                <p className="absolute -bottom-5 left-0 text-xs text-danger">{error}</p>
              )}
            </div>

            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="input-terminal w-32"
              disabled={loading}
            >
              <option value={90}>90 天</option>
              <option value={120}>120 天</option>
              <option value={180}>180 天</option>
              <option value={240}>240 天</option>
            </select>

            <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-1">
              <button
                type="button"
                className={`px-3 py-1 text-xs rounded-md transition-colors ${
                  mode === 'fast' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
                onClick={() => setMode('fast')}
                disabled={loading}
              >
                快速
              </button>
              <button
                type="button"
                className={`px-3 py-1 text-xs rounded-md transition-colors ${
                  mode === 'deep' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
                onClick={() => setMode('deep')}
                disabled={loading}
              >
                深度
              </button>
            </div>

            <button
              type="button"
              onClick={() => void fetchAdvice()}
              disabled={loading}
              className="btn-primary whitespace-nowrap"
            >
              {loading ? '计算中' : '提交分析'}
            </button>
          </div>
          <p className="text-xs text-slate-500">
            当前模式：{mode === 'deep' ? '深度（含新闻与大模型，耗时更长）' : '快速（技术面规则，秒级返回）'}
          </p>
        </div>
      </section>

      {!result && !loading && (
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white/70 p-10 text-center">
          <h2 className="text-base font-semibold text-slate-900">先输入基金代码</h2>
          <p className="text-sm text-slate-600 mt-2">
            推荐先试 `024195`、`017811`、`012414` 看看策略输出效果。
          </p>
        </section>
      )}

      {loading && (
        <section className="rounded-2xl border border-slate-200 bg-white p-10">
          <div className="flex items-center justify-center gap-2 text-slate-600">
            <div className="w-4 h-4 border-2 border-cyan/20 border-t-cyan rounded-full animate-spin" />
            {mode === 'deep' ? '正在执行深度基金分析...' : '正在计算基金建议...'}
          </div>
        </section>
      )}

      {result && !loading && (
        <div className="space-y-4 animate-fade-in">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">{result.fundName || result.fundCode}</h2>
                <p className="text-xs text-slate-500 mt-1">
                  输入: {result.fundCode} | 分析: {result.analysisCode}
                </p>
                {result.mappingNote && (
                  <p className="text-xs text-sky-700 mt-1">{result.mappingNote}</p>
                )}
              </div>

              <div className="text-right">
                <span className={`inline-flex items-center px-3 py-1 rounded-lg border text-sm ${actionClassName}`}>
                  {result.actionLabel}
                </span>
                <p className={`text-xs mt-2 ${confidenceClassName}`}>
                  置信度: {result.confidenceLevel} ({result.confidenceScore})
                </p>
                <p className="text-xs text-slate-500 mt-1">模式: {result.analysisMode === 'deep' ? '深度' : '快速'}</p>
                <p className="text-xs text-slate-500 mt-1">最新交易日: {result.latestDate}</p>
              </div>
            </div>
          </section>

          <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs text-slate-500">当前价格</p>
              <p className="text-xl font-semibold text-slate-900 mt-1">{fmt(result.currentPrice)}</p>
              <p className="text-xs text-slate-500 mt-2">
                MA5 {fmt(result.ma5)} | MA10 {fmt(result.ma10)} | MA20 {fmt(result.ma20)}
              </p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs text-slate-500">趋势与评分</p>
              <p className="text-base font-medium text-slate-900 mt-1">{result.trendStatus}</p>
              <p className="text-xs text-slate-500 mt-2">
                信号: {result.buySignal} | 综合评分: {result.signalScore}
              </p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs text-slate-500">量能状态</p>
              <p className="text-base font-medium text-slate-900 mt-1">{result.volumeStatus}</p>
              <p className="text-xs text-slate-500 mt-2">量比(5日): {fmt(result.volumeRatio5d, 2)}</p>
            </article>
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">MACD / RSI</h3>
              <p className="text-xs text-slate-500">
                DIF {fmt(result.macd?.dif)} | DEA {fmt(result.macd?.dea)} | BAR {fmt(result.macd?.bar)}
              </p>
              <p className="text-sm text-slate-900 mt-2">{result.macd?.status || '--'}</p>
              <p className="text-xs text-slate-500 mt-1">{result.macd?.signal || '--'}</p>
              <hr className="border-slate-200 my-3" />
              <p className="text-xs text-slate-500">
                RSI6 {fmt(result.rsi?.rsi6, 1)} | RSI12 {fmt(result.rsi?.rsi12, 1)} | RSI24 {fmt(result.rsi?.rsi24, 1)}
              </p>
              <p className="text-sm text-slate-900 mt-2">{result.rsi?.status || '--'}</p>
              <p className="text-xs text-slate-500 mt-1">{result.rsi?.signal || '--'}</p>
            </article>

            <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">规则判定</h3>
              <div className="space-y-1 text-sm">
                <p className="text-slate-700">
                  {result.ruleAssessment?.entryRule || '前大后小，金叉就搞'}：
                  <span className={result.ruleAssessment?.entryReady ? 'text-emerald-700' : 'text-slate-500'}>
                    {result.ruleAssessment?.entryReady ? '已满足' : '未满足'}
                  </span>
                </p>
                <p className="text-slate-700">
                  {result.ruleAssessment?.exitRule || '前高后低，放量就跑'}：
                  <span className={result.ruleAssessment?.exitTriggered ? 'text-rose-700' : 'text-slate-500'}>
                    {result.ruleAssessment?.exitTriggered ? '已触发' : '未触发'}
                  </span>
                </p>
              </div>
              <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                {result.ruleAssessment?.comment || '规则条件暂未满足，继续观察'}
              </p>
            </article>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">策略位建议</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-slate-500 text-xs">买入区间</p>
                <p className="mt-1 text-slate-900">
                  {fmt(result.strategy?.buyZone?.low)} - {fmt(result.strategy?.buyZone?.high)}
                </p>
                <p className="text-xs text-slate-500 mt-1">{result.strategy?.buyZone?.description || '--'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">加仓区间</p>
                <p className="mt-1 text-slate-900">
                  {fmt(result.strategy?.addZone?.low)} - {fmt(result.strategy?.addZone?.high)}
                </p>
                <p className="text-xs text-slate-500 mt-1">{result.strategy?.addZone?.description || '--'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">止损 / 止盈</p>
                <p className="mt-1 text-slate-900">
                  {fmt(result.strategy?.stopLoss)} / {fmt(result.strategy?.takeProfit)}
                </p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">仓位建议</p>
                <p className="mt-1 text-slate-900">{result.strategy?.positionAdvice || '--'}</p>
              </div>
            </div>
          </section>

          {result.analysisMode === 'deep' && (
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">深度分析</h3>
              {result.deepAnalysis?.status === 'completed' ? (
                <div className="space-y-3 text-sm">
                  <p className="text-slate-700">
                    {result.deepAnalysis.summary?.analysisSummary || '深度分析已完成，暂无摘要'}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">深度建议 / 趋势</p>
                      <p className="text-slate-900 mt-1">
                        {(result.deepAnalysis.summary?.operationAdvice || '--')} /{' '}
                        {(result.deepAnalysis.summary?.trendPrediction || '--')}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">情绪评分</p>
                      <p className="text-slate-900 mt-1">
                        {result.deepAnalysis.summary?.sentimentScore ?? '--'}{' '}
                        {result.deepAnalysis.summary?.sentimentLabel || ''}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">深度策略位</p>
                      <p className="text-slate-900 mt-1">
                        理想买点 {fmt(result.deepAnalysis.strategy?.idealBuy)} | 次级买点{' '}
                        {fmt(result.deepAnalysis.strategy?.secondaryBuy)}
                      </p>
                      <p className="text-slate-900 mt-1">
                        止损 {fmt(result.deepAnalysis.strategy?.stopLoss)} | 止盈{' '}
                        {fmt(result.deepAnalysis.strategy?.takeProfit)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">深度明细</p>
                      <p className="text-slate-700 mt-1 leading-relaxed">
                        {result.deepAnalysis.details?.newsSummary || '暂无新闻摘要'}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  深度分析暂不可用，已自动回退快速模式结果。
                  {result.deepAnalysis?.error ? ` 原因: ${result.deepAnalysis.error}` : ''}
                </div>
              )}
            </section>
          )}

          <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">做多依据</h3>
              {reasonItems.length > 0 ? (
                <ul className="space-y-1 text-sm text-slate-600 list-disc pl-4">
                  {reasonItems.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">暂无</p>
              )}
            </article>

            <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">风险提示</h3>
              {riskItems.length > 0 ? (
                <ul className="space-y-1 text-sm text-slate-600 list-disc pl-4">
                  {riskItems.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">暂无</p>
              )}
            </article>
          </section>
        </div>
      )}
    </div>
  );
};

export default FundAdvicePage;
