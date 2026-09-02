'use client';

import React, { ReactNode, useEffect, useRef } from 'react';
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

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

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
  /**
   * Accessible name for the dialog. Required context when no `title` is
   * given; falls back to a generic label so the dialog is never unnamed.
   */
  ariaLabel?: string;
}

/**
 * Shared responsive + accessible modal chrome.
 *
 - Overlay: fixed, centered, 16px edge gutter (`p-4`) so the panel never touches viewport edges.
 - Panel: `w-full` + per-size `max-w-*`, capped at `max-h-[calc(100vh-2rem)]`
   with `overflow-y-auto` so tall content scrolls internally and action
   buttons remain reachable on short viewports (phones, landscape).
 - Accessibility: `role="dialog"` + `aria-modal`; close button has an
   aria-label; Escape closes the topmost shell only; focus moves into the
   panel on open, is trapped while open (Tab cycles within the panel), and
   is restored to the trigger element on close.
 */
export function ModalShell({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  ariaLabel,
}: ModalShellProps): React.JSX.Element | null {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  // Keep the latest onClose without making it an effect dependency:
  // callers typically pass inline arrows, and re-running the focus/Escape
  // effect on every render would steal focus mid-interaction.
  const onCloseRef = useRef(onClose);
  // eslint-disable-next-line react-hooks/refs -- keep latest callback for focus restoration
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;
    const id = Symbol('modal-shell');
    MODAL_STACK.push(id);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (MODAL_STACK[MODAL_STACK.length - 1] !== id) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      // Focus trap: keep Tab cycling among the panel's focusable elements.
      if (e.key === 'Tab' && panelRef.current) {
        const focusables = Array.from(
          panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        ).filter((el) => el.offsetParent !== null || el === document.activeElement);
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (e.shiftKey && (active === first || !panelRef.current.contains(active))) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (active === last || !panelRef.current.contains(active))) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    // Move focus into the dialog so keyboard/SR users land inside it.
    // The panel itself (tabIndex=-1) is the safe target: no interactive
    // control receives unintended focus, Tab reaches the fields naturally.
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const raf = requestAnimationFrame(() => {
      panelRef.current?.focus();
    });

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      cancelAnimationFrame(raf);
      const idx = MODAL_STACK.indexOf(id);
      if (idx !== -1) MODAL_STACK.splice(idx, 1);
      // Restore focus to the trigger that opened this dialog.
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // The dismiss control must exist INDEPENDENTLY of the title: title-less
  // dialogs get a floating close button so pointer and screen-reader users
  // always have a visible way out (Escape alone is not discoverable).
  const closeButton = (
    <button
      type="button"
      onClick={onClose}
      aria-label="Close dialog"
      className={
        title
          ? 'p-1 -m-1 text-slate-400 hover:text-slate-700 rounded-lg transition cursor-pointer shrink-0'
          : 'absolute right-3 top-3 p-1 -m-1 text-slate-400 hover:text-slate-700 rounded-lg transition cursor-pointer shrink-0'
      }
    >
      <X className="w-5 h-5" />
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        // Accessible name: explicit ariaLabel wins; otherwise fall back to a
        // generic name when there is no title to derive one from.
        aria-label={ariaLabel ?? (title ? undefined : 'Dialog')}
        tabIndex={-1}
        className={`relative w-full ${SIZE_CLASSES[size]} bg-white rounded-2xl border border-slate-300 shadow-2xl p-4 sm:p-6 text-slate-900 max-h-[calc(100vh-2rem)] overflow-y-auto outline-none`}
      >
        {title ? (
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
            <div className="min-w-0 break-words">{title}</div>
            {closeButton}
          </div>
        ) : (
          closeButton
        )}

        <div className={title ? 'pt-4' : 'pt-2'}>{children}</div>

        {footer && (
          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
