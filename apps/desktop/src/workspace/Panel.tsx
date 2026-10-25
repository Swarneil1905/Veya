import { KeyboardEvent, ReactNode, useEffect, useRef } from 'react';
import { X } from '@phosphor-icons/react/dist/csr/X';

export function Panel({ open, title, onClose, children, kind = 'detail' }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; kind?: 'detail' | 'connection';
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open || !ref.current) return;
    const dialog = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog.showModal();
    const frame = requestAnimationFrame(() => dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus());
    return () => {
      cancelAnimationFrame(frame);
      dialog.close();
      if (opener?.isConnected) opener.focus();
      else document.getElementById('work-heading')?.focus();
    };
  }, [open]);
  function containFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return;
    const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button, input, textarea, select, a[href], [tabindex]')]
      .filter(element => element.tabIndex >= 0 && !element.matches(':disabled') && element.getClientRects().length > 0);
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  return <dialog ref={ref} className={`work-panel work-panel--${kind}`} aria-label={title}
    onKeyDown={containFocus}
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="work-panel-bar"><span>{title}</span><button type="button" className="work-icon-button" aria-label={`Close ${title.toLowerCase()}`} onClick={onClose}><X size={20} aria-hidden="true" /></button></header>
    {children}
  </dialog>;
}
