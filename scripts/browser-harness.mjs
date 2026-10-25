import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';

const root = path.resolve('apps/desktop/dist');
export async function asset(request, response) {
  try {
    const url = new URL(request.url, 'http://localhost');
    const relative = decodeURIComponent(url.pathname).replace(/^\/+/, '') || 'index.html';
    const file = path.resolve(root, relative);
    if (!file.startsWith(root + path.sep)) {
      response.writeHead(404).end();
      return;
    }
    const types = {
      '.html': 'text/html',
      '.js': 'text/javascript',
      '.css': 'text/css',
      '.woff2': 'font/woff2',
      '.woff': 'font/woff',
      '.svg': 'image/svg+xml',
    };
    response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
    response.end(await readFile(file));
  } catch {
    response.writeHead(404).end();
  }
}
export async function harness() {
  const server = http.createServer(asset);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({
    executablePath:
      process.env.VEYA_CHROME ||
      (process.platform === 'win32'
        ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        : undefined),
    headless: true,
  });
  return {
    browser,
    origin: `http://127.0.0.1:${server.address().port}`,
    close: async () => {
      await browser.close();
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

// Browser fixtures may contact only their owned loopback origin. Block before DNS.
export async function isolate(context, origin) {
  const permitted = new URL(origin).origin;
  if (new URL(origin).hostname !== '127.0.0.1') throw new Error('Fixture origin must be loopback');
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.origin === permitted ? route.continue() : route.abort('blockedbyclient');
  });
  await context.routeWebSocket('**/*', socket => socket.close());
}
