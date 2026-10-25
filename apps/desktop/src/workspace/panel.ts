import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
  ViewChild,
} from '@angular/core';

@Component({
  selector: 'veya-panel',
  template: ` <dialog
    #dialog
    class="work-panel"
    [class.work-panel--connection]="kind === 'connection'"
    [class.work-panel--detail]="kind === 'detail'"
    [attr.aria-label]="title"
    (cancel)="cancel($event)"
    (keydown)="containFocus($event)"
  >
    <header class="work-panel-bar">
      <span>{{ title }}</span
      ><button
        type="button"
        class="work-icon-button"
        [attr.aria-label]="'Close ' + title.toLowerCase()"
        (click)="closed.emit()"
      >
        <i class="ph ph-x" aria-hidden="true"></i>
      </button>
    </header>
    <ng-content />
  </dialog>`,
})
export class Panel implements AfterViewInit, OnDestroy {
  @Input() title = '';
  @Input() kind: 'detail' | 'connection' = 'detail';
  @Output() closed = new EventEmitter<void>();
  @ViewChild('dialog') dialog!: ElementRef<HTMLDialogElement>;
  private opener: HTMLElement | null = null;
  private frame = 0;
  ngAfterViewInit() {
    this.opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    this.dialog.nativeElement.showModal();
    this.frame = requestAnimationFrame(() =>
      this.dialog.nativeElement.querySelector<HTMLElement>('[data-autofocus]')?.focus(),
    );
  }
  ngOnDestroy() {
    cancelAnimationFrame(this.frame);
    this.dialog.nativeElement.close();
    if (this.opener?.isConnected) this.opener.focus();
    else document.getElementById('work-heading')?.focus();
  }
  cancel(event: Event) {
    event.preventDefault();
    this.closed.emit();
  }
  containFocus(event: KeyboardEvent) {
    if (event.key !== 'Tab') return;
    const controls = [
      ...this.dialog.nativeElement.querySelectorAll<HTMLElement>(
        'button,input,textarea,select,a[href],[tabindex]',
      ),
    ].filter(
      (el) => el.tabIndex >= 0 && !el.matches(':disabled') && el.getClientRects().length > 0,
    );
    const first = controls[0],
      last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
}
