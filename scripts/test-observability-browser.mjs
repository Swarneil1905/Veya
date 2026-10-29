import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { isolate } from './browser-harness.mjs';
const origin = process.argv[2];
assert.match(origin,/^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch({headless:true,executablePath:process.env.VEYA_CHROME || (process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined)});
try {
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
  await isolate(context,origin);
  const page=await context.newPage();
  await page.goto(origin+'/d/veya-runtime/veya-runtime-operations?from=now-5m&to=now&refresh=5s');
  await page.getByText('Failure ratio by source',{exact:true}).waitFor({timeout:30000});
  await page.getByRole('heading',{name:'Calls with unknown cost',exact:true}).waitFor();
  await page.getByText('provider',{exact:true}).first().waitFor();
  assert.equal(await page.getByText('Datasource not found',{exact:false}).count(),0);
  await page.screenshot({path:'artifacts/operations20/dashboard/rendered.png',fullPage:true});
  await page.mouse.move(1000,800);
  await page.mouse.wheel(0,1400);
  await page.getByRole('heading',{name:'Budget exhaustion',exact:true}).waitFor();
  await page.screenshot({path:'artifacts/operations20/dashboard/rendered-bottom.png'});
  console.log('PASS: provisioned Grafana dashboard renders synthetic provider failure and unknown-cost panels');
} finally { await browser.close(); }
