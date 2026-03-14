import React from 'react';
import type { AnalysisResult, AnalysisReport } from '../../types/analysis';
import { ReportOverview } from './ReportOverview';
import { ReportStrategy } from './ReportStrategy';
import { ReportNews } from './ReportNews';
import { ReportDetails } from './ReportDetails';
import { Card } from '../common';

interface ReportSummaryProps {
  data: AnalysisResult | AnalysisReport;
  isHistory?: boolean;
}

/**
 * 完整报告展示组件
 * 整合概览、策略、资讯、详情四个区域
 */
export const ReportSummary: React.FC<ReportSummaryProps> = ({
  data,
  isHistory = false,
}) => {
  // 兼容 AnalysisResult 和 AnalysisReport 两种数据格式
  const report: AnalysisReport | null = 'report' in data ? data.report : data;

  if (!report || !report.meta || !report.summary) {
    return (
      <Card variant="bordered" padding="md">
        <div className="text-left">
          <h3 className="text-sm font-medium text-warning">报告数据不完整</h3>
          <p className="text-xs text-secondary mt-1">当前记录缺少必要字段，暂时无法渲染详情。</p>
        </div>
      </Card>
    );
  }

  const queryId = 'queryId' in data ? data.queryId : report.meta.queryId;

  const { meta, summary, strategy, details } = report;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* 概览区（首屏） */}
      <ReportOverview
        meta={meta}
        summary={summary}
        isHistory={isHistory}
      />

      {/* 策略点位区 */}
      <ReportStrategy strategy={strategy} />

      {/* 资讯区 */}
      <ReportNews queryId={queryId} />

      {/* 透明度与追溯区 */}
      <ReportDetails details={details} queryId={queryId} />
    </div>
  );
};
