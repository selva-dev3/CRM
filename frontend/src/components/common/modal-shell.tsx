'use client';

import React, { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
};

/**
 * Tracks open ModalShells so Escape only closes the topmost one
 * (prevents stacked dialogs all closing from a single Escape press).
 */
const MODAL_STACK: symbol[] = [];

export interface ModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  /** Optional header content (rendered inside the scrollable panel, next to the close button). */
  title?: ReactNode;
  /** Body content. Form action rows stay INSIDE the form here so type="submit" keeps working. */
  children: ReactNode;
  /** Optional footer rendered below children — only use when actions do NOT need form context. */
  footer?: ReactNode;
  size?: ModalSize;
}

/**
 * Shared responsive modal chrome.
 *
 - Overlay: fixed, centered, 16px edge gutter (`p-4`) so the panel never touches viewport edges.
 - Panel: `w-full` + per-size `max-w-*`, capped at `max-h-[calc(100vh-2rem)]`
   with `overflow-y-auto` so tall content scrolls internally and action
   buttons remain reachable on short viewports (phones, landscape).
 - Close button is a real `<button>` with aria-label; Escape closes the
   topmost shell only; `role="dialog"` + `aria-modal` for assistive tech.
 */
export function ModalShell({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
}: ModalShellProps): React.JSX.Element | null {
  useEffect(() => {
    if (!isOpen) return;
    const id = Symbol('modal-shell');
    MODAL_STACK.push(id);
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && MODAL_STACK[MODAL_STACK.length - 1] === id) {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      const idx = MODAL_STACK.indexOf(id);
      if (idx !== -1) MODAL_STACK.splice(idx, 1);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
      <div
        role="dialog"
        aria-modal="true"
        className={`relative w-full ${SIZE_CLASSES[size]} bg-white rounded-2xl border border-slate-300 shadow-2xl p-4 sm:p-6 text-slate-900 max-h-[calc(100vh-2rem)] overflow-y-auto`}
      >
        {title && (
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
            <div className="min-w-0 break-words">{title}</div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="p-1 -m-1 text-slate-400 hover:text-slate-700 rounded-lg transition cursor-pointer shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        <div className={title ? 'pt-4' : undefined}>{children}</div>

        {footer && (
          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
