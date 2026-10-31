import { Component } from '@angular/core';
import { BrandMark } from '../../ui/brand-mark';

@Component({
  selector: 'veya-work-welcome',
  imports: [BrandMark],
  host: { 'aria-hidden': 'true' },
  template: `<div class="scene">
    <div class="stack">
      <div class="sheet sheet-back"></div>
      <div class="sheet sheet-middle"></div>
      <div class="sheet sheet-front">
        <veya-brand-mark />
        <span class="paper-line"></span><span class="paper-line short"></span>
        <div class="paper-divider"></div>
        <span class="paper-line"></span><span class="paper-line short"></span>
      </div>
      <div class="glass-seal"><i class="ph ph-tray"></i></div>
    </div>
  </div>`,
  styleUrl: './work-welcome.css',
})
export class WorkWelcome {}
