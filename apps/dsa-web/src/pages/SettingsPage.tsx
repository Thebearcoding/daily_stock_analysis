import type React from 'react';
import { useEffect } from 'react';
import { useAuth, useSystemConfig } from '../hooks';
import { ApiErrorAlert } from '../components/common';
import {
  ChangePasswordCard,
  IntelligentImport,
  LLMChannelEditor,
  SettingsAlert,
  SettingsField,
  SettingsLoading,
} from '../components/settings';
import { getCategoryDescriptionZh, getCategoryTitleZh } from '../utils/systemConfigI18n';

const SettingsPage: React.FC = () => {
  const { passwordChangeable } = useAuth();
  const {
    categories,
    itemsByCategory,
    issueByKey,
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount,
    toast,
    clearToast,
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,
    load,
    retry,
    save,
    setDraftValue,
    configVersion,
    maskToken,
  } = useSystemConfig();

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 3200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  const rawActiveItems = itemsByCategory[activeCategory] || [];
  const rawActiveItemMap = new Map(rawActiveItems.map((item) => [item.key, String(item.value ?? '')]));
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());

  // Hide channel-managed and legacy provider-specific LLM keys from the
  // generic form only when channel config is the active runtime source.
  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const AI_MODEL_HIDDEN_KEYS = new Set([
    'LLM_CHANNELS',
    'LLM_TEMPERATURE',
    'LITELLM_MODEL',
    'LITELLM_FALLBACK_MODELS',
    'AIHUBMIX_KEY',
    'DEEPSEEK_API_KEY',
    'DEEPSEEK_API_KEYS',
    'GEMINI_API_KEY',
    'GEMINI_API_KEYS',
    'GEMINI_MODEL',
    'GEMINI_MODEL_FALLBACK',
    'GEMINI_TEMPERATURE',
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_API_KEYS',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_TEMPERATURE',
    'ANTHROPIC_MAX_TOKENS',
    'OPENAI_API_KEY',
    'OPENAI_API_KEYS',
    'OPENAI_BASE_URL',
    'OPENAI_MODEL',
    'OPENAI_VISION_MODEL',
    'OPENAI_TEMPERATURE',
    'VISION_MODEL',
  ]);
  const activeItems =
    activeCategory === 'ai_model'
      ? rawActiveItems.filter((item) => {
        if (hasConfiguredChannels && LLM_CHANNEL_KEY_RE.test(item.key)) {
          return false;
        }
        if (hasConfiguredChannels && !hasLitellmConfig && AI_MODEL_HIDDEN_KEYS.has(item.key)) {
          return false;
        }
        return true;
      })
      : rawActiveItems;

  return (
    <div className="min-h-screen bg-warm-bg text-charcoal font-sans selection:bg-clay/20 selection:text-charcoal flex flex-col pt-6 md:pt-10">
      <div className="max-w-[1400px] w-full mx-auto flex flex-col gap-6 px-4 md:px-8 pb-12">

        {/* Page Header */}
        <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-serif text-charcoal mb-2 tracking-tight">系统设置</h1>
            <p className="text-sm text-charcoal-muted max-w-xl">
              管理运行参数、模型渠道、通知方式与系统级配置。默认值来自 `.env`。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
            <button type="button" className="btn-secondary" onClick={() => void load()} disabled={isLoading || isSaving}>
              重置
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void save()}
              disabled={!hasDirty || isSaving || isLoading}
            >
              {isSaving ? '保存中...' : `保存配置${dirtyCount ? ` (${dirtyCount})` : ''}`}
            </button>
          </div>
        </header>

        {saveError ? (
          <ApiErrorAlert
            error={saveError}
            actionLabel={retryAction === 'save' ? '重试保存' : undefined}
            onAction={retryAction === 'save' ? () => void retry() : undefined}
          />
        ) : null}

        {loadError ? (
          <ApiErrorAlert
            error={loadError}
            actionLabel={retryAction === 'load' ? '重试加载' : '重新加载'}
            onAction={() => void retry()}
          />
        ) : null}

        {isLoading ? (
          <SettingsLoading />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
            {/* Sidebar */}
            <aside className="glass-panel rounded-2xl p-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-charcoal-muted">配置分类</p>
              <div className="space-y-1.5">
                {categories.map((category) => {
                  const isActive = category.category === activeCategory;
                  const count = (itemsByCategory[category.category] || []).length;
                  const title = getCategoryTitleZh(category.category, category.title);
                  const description = getCategoryDescriptionZh(category.category, category.description);

                  return (
                    <button
                      key={category.category}
                      type="button"
                      className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition-all duration-200 ${
                        isActive
                          ? 'border-charcoal bg-charcoal text-warm-bg shadow-sm'
                          : 'border-transparent bg-transparent text-charcoal-muted hover:bg-warm-surface-alt hover:text-charcoal'
                      }`}
                      onClick={() => setActiveCategory(category.category)}
                    >
                      <span className="flex items-center justify-between text-sm font-medium">
                        {title}
                        <span className={`text-xs ${isActive ? 'text-warm-bg/75' : 'text-charcoal-muted'}`}>{count}</span>
                      </span>
                      {description ? (
                        <span className={`mt-0.5 block text-xs leading-relaxed ${isActive ? 'text-warm-bg/70' : 'text-charcoal-muted'}`}>
                          {description}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </aside>

            {/* Content */}
            <section className="glass-panel rounded-2xl p-5 md:p-6 space-y-4">
              {activeCategory === 'base' ? (
                <div className="space-y-4">
                  <IntelligentImport
                    stockListValue={
                      (activeItems.find((i) => i.key === 'STOCK_LIST')?.value as string) ?? ''
                    }
                    configVersion={configVersion}
                    maskToken={maskToken}
                    onMerged={() => void load()}
                    disabled={isSaving || isLoading}
                  />
                </div>
              ) : null}
              {activeCategory === 'ai_model' ? (
                <LLMChannelEditor
                  items={rawActiveItems}
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onSaved={() => void load()}
                  disabled={isSaving || isLoading}
                />
              ) : null}
              {activeCategory === 'system' && passwordChangeable ? (
                <div className="space-y-4">
                  <ChangePasswordCard />
                </div>
              ) : null}
              {activeItems.length ? (
                activeItems.map((item) => (
                  <SettingsField
                    key={item.key}
                    item={item}
                    value={item.value}
                    disabled={isSaving}
                    onChange={setDraftValue}
                    issues={issueByKey[item.key] || []}
                  />
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-warm-border/60 bg-warm-surface/30 p-8 text-center text-sm text-charcoal-muted">
                  当前分类下暂无配置项。
                </div>
              )}
            </section>
          </div>
        )}

        {toast ? (
          <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
            {toast.type === 'success'
              ? <SettingsAlert title="操作成功" message={toast.message} variant="success" />
              : <ApiErrorAlert error={toast.error} />}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default SettingsPage;
