import { Component, Input } from '@angular/core';

// Decorative surface only: the enclosing button owns its name and interaction.
@Component({
  selector: 'veya-glass-icon',
  host: { 'aria-hidden': 'true' },
  template: `<i [class]="'ph ph-' + name"></i>`,
  styleUrl: './glass-icon.css',
})
export class GlassIcon {
  @Input({ required: true }) name!: string;
}
