'use client';

import { useRef, type ReactNode, type RefObject } from 'react';
import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-md',
  lg: 'sm:max-w-lg',
  xl: 'sm:max-w-xl',
  '2xl': 'sm:max-w-2xl',
  '3xl': 'sm:max-w-3xl',
};

export interface ModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: ModalSize;
  ariaLabel?: string;
  contentClassName?: string;
  bodyClassName?: string;
  initialFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * Compatibility wrapper for feature dialogs.
 *
 * Radix Dialog owns focus trapping, focus restoration, Escape handling,
 * stacking and portal behavior. The public API remains unchanged so feature
 * forms retain their existing submission flow.
 */
export function ModalShell({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  ariaLabel,
  contentClassName,
  bodyClassName,
  initialFocusRef,
}: ModalShellProps): React.JSX.Element {
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const accessibleTitle =
    ariaLabel ?? (typeof title === 'string' ? title : 'Dialog');

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        aria-label={accessibleTitle}
        onOpenAutoFocus={(event) => {
          restoreFocusRef.current = document.activeElement as HTMLElement | null;
          if (initialFocusRef?.current) {
            event.preventDefault();
            initialFocusRef.current.focus();
          }
        }}
        onPointerDownOutside={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocusRef.current?.focus();
        }}
        className={cn(
          'max-h-[calc(100dvh-2rem)] gap-0 overflow-y-auto rounded-2xl border-slate-300 p-4 text-slate-900 shadow-2xl sm:p-6',
          SIZE_CLASSES[size],
          contentClassName,
        )}
      >
        <DialogTitle className="sr-only">{accessibleTitle}</DialogTitle>

        {title ? (
          <DialogHeader className="flex-row items-start justify-between gap-3 border-b border-slate-100 pb-3 text-left">
            <div className="min-w-0 flex-1 break-words">{title}</div>
            <DialogClose asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Close dialog"
                className="-m-1 shrink-0 text-slate-400 hover:text-slate-700"
              >
                <X className="size-5" />
              </Button>
            </DialogClose>
          </DialogHeader>
        ) : (
          <DialogClose asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Close dialog"
              className="absolute right-3 top-3 text-slate-400 hover:text-slate-700"
            >
              <X className="size-5" />
            </Button>
          </DialogClose>
        )}

        <div className={cn(title ? 'pt-4' : 'pt-2', bodyClassName)}>{children}</div>

        {footer && (
          <DialogFooter className="items-stretch gap-2 pt-2 sm:items-center sm:gap-3">
            {footer}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
