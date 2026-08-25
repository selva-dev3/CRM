'use client';

import React, { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModalShell } from '@/components/common/modal-shell';

export interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: string;
  message?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'default';
  isLoading?: boolean;
  icon?: ReactNode;
}

/**
 * Confirmation dialog for destructive/important actions.
 *
 * Built on ModalShell so every confirm dialog inherits the shared
 * accessibility contract (role="dialog", Escape-to-close, focus trap and
 * focus restore) plus the responsive scroll-safe layout. The public API is
 * unchanged from the original hand-rolled version; delete flows keep
 * passing the same props.
 */
export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description = 'This action cannot be undone.',
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  isLoading = false,
  icon,
}: ConfirmModalProps): React.JSX.Element | null {
  const variantStyles = {
    danger: {
      iconBg: 'bg-rose-100 text-rose-600',
      btnBg: 'bg-rose-600 hover:bg-rose-700 text-white',
      defaultIcon: <Trash2 className="w-5 h-5" />,
    },
    warning: {
      iconBg: 'bg-amber-100 text-amber-600',
      btnBg: 'bg-amber-600 hover:bg-amber-700 text-white',
      defaultIcon: <AlertTriangle className="w-5 h-5" />,
    },
    default: {
      iconBg: 'bg-blue-100 text-blue-600',
      btnBg: 'bg-blue-600 hover:bg-blue-700 text-white',
      defaultIcon: <AlertCircle className="w-5 h-5" />,
    },
  };

  const style = variantStyles[variant];

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${style.iconBg}`}>
            {icon || style.defaultIcon}
          </div>
          <div className="min-w-0">
            <h3 className="text-sm sm:text-base font-bold text-slate-900 break-words">{title}</h3>
            {description && <p className="text-xs text-slate-500">{description}</p>}
          </div>
        </div>
      }
      footer={
        <>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isLoading}
            className="text-xs cursor-pointer border-slate-300 w-full sm:w-auto"
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={isLoading}
            onClick={onConfirm}
            className={`text-xs font-semibold cursor-pointer w-full sm:w-auto ${style.btnBg}`}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Processing...</span>
              </span>
            ) : (
              confirmText
            )}
          </Button>
        </>
      }
    >
      {message && (
        <div className="text-xs font-medium text-slate-700 break-words -mt-1">{message}</div>
      )}
    </ModalShell>
  );
}
