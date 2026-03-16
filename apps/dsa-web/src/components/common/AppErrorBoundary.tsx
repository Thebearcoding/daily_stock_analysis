import React from 'react';

interface AppErrorBoundaryProps {
  children: React.ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
  message?: string;
}

/**
 * 全局错误边界，避免运行时异常导致整页黑屏。
 */
export class AppErrorBoundary extends React.Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  constructor(props: AppErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: unknown): AppErrorBoundaryState {
    const message = error instanceof Error ? error.message : '未知错误';
    return {
      hasError: true,
      message,
    };
  }

  componentDidCatch(error: unknown): void {
    console.error('AppErrorBoundary caught error:', error);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): React.ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="max-w-xl rounded-2xl glass-panel p-6 text-left shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-red-500">Rendering Error</p>
          <h2 className="mt-2 text-xl font-serif font-semibold text-charcoal">页面渲染异常，已阻止黑屏</h2>
          <p className="mt-2 text-sm text-charcoal-muted">
            可以先刷新页面继续使用。如果问题反复出现，请把这条错误信息发给我继续修复。
          </p>
          {this.state.message && (
            <pre className="mt-4 overflow-x-auto rounded-lg bg-warm-surface-alt border border-warm-border p-3 text-xs text-charcoal font-mono">
              {this.state.message}
            </pre>
          )}
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-4 inline-flex items-center rounded-lg bg-charcoal px-4 py-2 text-sm font-medium text-white hover:bg-[#333333] transition-colors"
          >
            刷新页面
          </button>
        </div>
      </div>
    );
  }
}

export default AppErrorBoundary;
