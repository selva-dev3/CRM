'use client';

import React, { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Loader2, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

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
  if (!isOpen) return null;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
      <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-4 sm:p-6 space-y-4 text-slate-900 max-h-[calc(100vh-2rem)] overflow-y-auto">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${style.iconBg}`}>
              {icon || style.defaultIcon}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm sm:text-base font-bold text-slate-900 break-words">{title}</h3>
              {description && <p className="text-xs text-slate-500">{description}</p>}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="p-1 text-slate-400 hover:text-slate-700 rounded-lg transition cursor-pointer shrink-0"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {message && <div className="text-xs font-medium text-slate-700 break-words">{message}</div>}

        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
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
        </div>
      </div>
    </div>
  );
}
