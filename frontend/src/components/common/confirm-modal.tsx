'use client';

import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Loader2, Trash2 } from 'lucide-react';

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
}: ConfirmModalProps): React.JSX.Element {
  const variantStyles = {
    danger: {
      iconBg: 'bg-rose-100 text-rose-600',
      button: 'bg-rose-600 text-white hover:bg-rose-700',
      defaultIcon: <Trash2 className="size-5" />,
    },
    warning: {
      iconBg: 'bg-amber-100 text-amber-600',
      button: 'bg-amber-600 text-white hover:bg-amber-700',
      defaultIcon: <AlertTriangle className="size-5" />,
    },
    default: {
      iconBg: 'bg-blue-100 text-blue-600',
      button: 'bg-blue-600 text-white hover:bg-blue-700',
      defaultIcon: <AlertCircle className="size-5" />,
    },
  } as const;
  const styles = variantStyles[variant];

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader className="sm:grid-cols-[auto_1fr] sm:gap-x-3">
          <div
            className={cn(
              'flex size-10 shrink-0 items-center justify-center rounded-full',
              styles.iconBg
            )}
          >
            {icon ?? styles.defaultIcon}
          </div>
          <div className="min-w-0">
            <AlertDialogTitle className="break-words text-sm sm:text-base">
              {title}
            </AlertDialogTitle>
            {description && (
              <AlertDialogDescription className="mt-1 text-xs">
                {description}
              </AlertDialogDescription>
            )}
          </div>
        </AlertDialogHeader>

        {message && (
          <div className="break-words text-xs font-medium text-slate-700">
            {message}
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel
            size="sm"
            disabled={isLoading}
            className="w-full border-slate-300 text-xs sm:w-auto"
          >
            {cancelText}
          </AlertDialogCancel>
          <Button
            type="button"
            size="sm"
            disabled={isLoading}
            onClick={onConfirm}
            className={cn('w-full text-xs font-semibold sm:w-auto', styles.button)}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-1.5">
                <Loader2 className="size-3.5 animate-spin" />
                Processing...
              </span>
            ) : (
              confirmText
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
