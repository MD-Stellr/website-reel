import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
const [url, out, w, h] = [process.argv[2], process.argv[3], +process.argv[4], +process.argv[5]];
fs.mkdirSync(path.dirname(out), { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);
const H = await page.evaluate(() => document.documentElement.scrollHeight);
// scroll through in real time to trigger reveals
for (let y = 0; y < H; y += 300) { await page.evaluate(y => window.scrollTo(0, y), y); await page.waitForTimeout(120); }
await page.waitForTimeout(1500);
const sections = await page.evaluate(() => [...document.querySelectorAll('section, h1, h2, video, canvas')].map(e => {
  const r = e.getBoundingClientRect(); return { tag: e.tagName, top: Math.round(r.top + scrollY), h: Math.round(r.height), text: (e.innerText||'').replace(/\s+/g,' ').slice(0,60) };
}));
console.log('height', H); console.log(sections.map(s => `${s.tag.padEnd(7)} top=${String(s.top).padStart(6)} h=${String(s.h).padStart(5)} ${s.text}`).join('\n'));
// viewport screenshots down the page for a contact sheet
let i = 0;
for (let y = 0; y < H; y += h) { await page.evaluate(y => window.scrollTo(0, y), y); await page.waitForTimeout(700); await page.screenshot({ path: `${out}-${String(i++).padStart(2,'0')}.png` }); }
await browser.close();
