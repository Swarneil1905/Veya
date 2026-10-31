import { Component } from '@angular/core';

@Component({
  selector: 'veya-brand-mark',
  host: { 'aria-hidden': 'true' },
  template: `<svg viewBox="0 0 32 32" fill="none" focusable="false">
    <path d="M3 6h7l8 19h-7L3 6Z" fill="currentColor"/>
    <path d="M22 6h7L18 26h-7L22 6Z" fill="currentColor" opacity=".72"/>
  </svg>`,
  styles: `:host{display:inline-flex;width:28px;height:28px;flex:none;color:var(--work-accent)}svg{width:100%;height:100%}`,
})
export class BrandMark {}
