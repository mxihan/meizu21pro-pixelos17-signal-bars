// Run with NODE_PATH pointing to an installed Playwright package directory.
// Only the native bridge is substituted; the shipped SDK, parser, DOM and styles run unchanged.
const { chromium } = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../module/webroot');
const fixture = fs.readFileSync(path.resolve(__dirname, 'fixtures/status.txt'), 'utf8');
const server = http.createServer((req, res) => {
  const name = req.url === '/' ? 'index.html' : req.url.slice(1);
  const file = path.resolve(root, name);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
  const ext = path.extname(file);
  res.setHeader('Content-Type', ({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css'})[ext] || 'text/plain');
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: {width:391, height:912}, colorScheme:'light' });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(data => {
      window.bridgeCalls = 0;
      window.bridgeData = data;
      window.ksu = { exec(command, options, callback) {
        window.bridgeCalls++;
        if (window.bridgeFail) window[callback](1, '', 'permission denied');
        else window[callback](0, window.bridgeData, '');
      } };
    }, fixture);
    const url = `http://127.0.0.1:${server.address().port}/`;
    await page.goto(url);
    await page.getByText('运行正常', {exact:true}).waitFor();
    assert.equal(await page.locator('#wifi-bars').getAttribute('aria-label'), '2 / 3 格');
    assert.equal(await page.getByText('NR SS-RSRP', {exact:true}).count(), 1);
    assert.ok((await page.locator('#phones').innerText()).includes('-110'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path:path.resolve(__dirname, '../verification/webui-light.png'),fullPage:true});
    await page.emulateMedia({colorScheme:'dark'});
    await page.screenshot({path:path.resolve(__dirname, '../verification/webui-dark.png'),fullPage:true});
    await page.getByRole('button', {name:'刷新',exact:true}).click();
    await page.waitForFunction(() => window.bridgeCalls >= 2);
    await page.waitForTimeout(10500);
    assert.ok(await page.evaluate(() => window.bridgeCalls >= 3), 'visible page did not auto-refresh');
    await page.evaluate(() => { window.bridgeFail = true; });
    await page.getByRole('button', {name:'刷新',exact:true}).click();
    await page.getByText('刷新失败 · 显示内容可能已过时', {exact:true}).waitFor();
    assert.ok(await page.locator('#snapshot').evaluate(el => el.classList.contains('stale')));
    await page.evaluate(() => { window.bridgeFail = false; });
    await page.getByRole('button', {name:'刷新',exact:true}).click();
    await page.waitForFunction(() => !document.querySelector('#snapshot').classList.contains('stale'));
    await page.evaluate(() => { window.bridgeData = window.bridgeData.replace('[x] io.github.rin.meizu21pro.signalbars.wifi', '[ ] io.github.rin.meizu21pro.signalbars.wifi'); });
    await page.getByRole('button', {name:'刷新',exact:true}).click();
    await page.waitForFunction(() => !document.querySelector('#refresh').disabled);
    assert.notEqual(await page.locator('#health').innerText(), '运行正常', 'disabled overlay must not be reported healthy');
    assert.deepEqual(errors, []);
    const plain = await browser.newPage({viewport:{width:320,height:700}});
    await plain.goto(url);
    await plain.getByText('请从 KernelSU 的模块 WebUI 打开此页。', {exact:true}).waitFor();
    assert.equal(await plain.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    console.log('Browser checks passed: mobile layout, SDK callback, manual/auto refresh, stale-data recovery, missing bridge, light/dark themes.');
  } finally { if (browser) await browser.close(); server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
