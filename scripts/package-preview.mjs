import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
const root = path.resolve('apps/desktop/dist');
const html = readFileSync(path.join(root, 'index.html'), 'utf8');
const script = html.match(/<script[^>]+src="([^"]+)"[^>]*><\/script>/);
const style = html.match(/<link[^>]+href="([^"]+\.css)"[^>]*>/);
if (!script || !style) throw new Error('Built Angular assets not found.');
const asset = (name) => path.join(root, name.replace(/^\//, ''));
const js = readFileSync(asset(script[1]), 'utf8').replaceAll('</script', '<\\/script');
const css = readFileSync(asset(style[1]), 'utf8').replace(/url\(([^)]+)\)/g, (_match, value) => {
  const name = value.replace(/^["']|["']$/g, '');
  if (name.startsWith('data:')) return `url(${value})`;
  const [filename, fragment] = name.split('#');
  const file = asset(filename),
    type = {
      '.woff2': 'font/woff2',
      '.woff': 'font/woff',
      '.ttf': 'font/ttf',
      '.svg': 'image/svg+xml',
    }[path.extname(file)];
  if (!type || !file.startsWith(root + path.sep)) throw Error('Unsupported preview asset');
  return `url(data:${type};base64,${readFileSync(file).toString('base64')}${fragment ? '#' + fragment : ''})`;
});
const bundled = html
  .replace(script[0], () => `<script type="module">${js}</script>`)
  .replace(style[0], () => `<style>${css}</style>`);
mkdirSync('preview', { recursive: true });
writeFileSync('preview/Veya-Preview.html', bundled);
console.log('Created self-contained Angular workspace preview, including licensed fonts/icons.');
