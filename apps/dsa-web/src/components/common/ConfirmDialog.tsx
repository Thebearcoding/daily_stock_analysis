import type React from 'react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Generic confirmation dialog component.
 * Style is consistent with ChatPage.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText = '确定',
  cancelText = '取消',
  isDanger = false,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/20 backdrop-blur-sm transition-all"
      onClick={onCancel}
    >
      <div
        className="glass-panel rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl animate-in fade-in zoom-in duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-charcoal font-medium mb-2 text-lg">{title}</h3>
        <p className="text-sm text-charcoal-muted mb-6 leading-relaxed">
          {message}
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm font-medium text-charcoal-muted hover:text-charcoal hover:bg-warm-surface-alt border border-warm-border transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              isDanger
                ? 'bg-red-500/10 text-red-600 hover:bg-red-500/20 hover:text-red-700 font-semibold'
                : 'bg-charcoal text-white hover:bg-[#333333]'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
