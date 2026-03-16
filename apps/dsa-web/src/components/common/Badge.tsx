import React from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  glow?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-warm-surface-alt text-charcoal-muted border-warm-border/50',
  success: 'bg-emerald-50 text-emerald-600 border-emerald-200',
  warning: 'bg-amber-50 text-amber-600 border-amber-200',
  danger: 'bg-red-50 text-red-600 border-red-200',
  info: 'bg-clay/10 text-clay border-clay/20',
  history: 'bg-purple/10 text-purple border-purple/20',
};

const glowStyles: Record<BadgeVariant, string> = {
  default: '',
  success: 'shadow-emerald-500/10',
  warning: 'shadow-amber-500/10',
  danger: 'shadow-red-500/10',
  info: 'shadow-clay/10',
  history: 'shadow-purple/10',
};

/**
 * 标签徽章组件
 * 支持多种变体和发光效果
 */
export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'sm',
  glow = false,
  className = '',
}) => {
  const sizeStyles = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-full font-medium
        border backdrop-blur-sm
        ${sizeStyles}
        ${variantStyles[variant]}
        ${glow ? `shadow-lg ${glowStyles[variant]}` : ''}
        ${className}
      `}
    >
      {children}
    </span>
  );
};
