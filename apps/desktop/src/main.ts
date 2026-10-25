import { bootstrapApplication } from '@angular/platform-browser';
import { Workspace } from './workspace/workspace';
bootstrapApplication(Workspace).catch(() => {
  document.body.textContent = 'Veya could not start. Reload to try again.';
});
