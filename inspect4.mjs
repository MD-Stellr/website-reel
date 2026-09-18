import { chromium } from 'playwright';
const [url, w, h] = [process.argv[2], +process.argv[3], +process.argv[4]];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: w, height: h } });
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(3000);
const out = await page.evaluate(() => {
  const H = document.documentElement.scrollHeight;
  const secs = [...document.querySelectorAll('section')].map(s => {
    const r = s.getBoundingClientRect(); const pin = [...s.querySelectorAll('*')].some(e => getComputedStyle(e).position === 'sticky' && e.getBoundingClientRect().height > innerHeight * 0.6);
    return `${String(Math.round(r.top + scrollY)).padStart(6)} h=${String(Math.round(r.height)).padStart(5)}${pin ? ' [pinned]' : ''}  ${(s.innerText || '').replace(/\s+/g, ' ').slice(0, 50)}`;
  });
  const vids = [...document.querySelectorAll('video')].map(v => ({ autoplay: v.autoplay, loop: v.loop, paused: v.paused, src: (v.currentSrc || '').slice(-40) }));
  return { H, maxScroll: H - innerHeight, secs, vids, canv: document.querySelectorAll('canvas').length };
});
console.log(`${url} @${w}x${h}: height ${out.H}, max scroll ${out.maxScroll}, canvases ${out.canv}, videos ${JSON.stringify(out.vids)}`);
console.log(out.secs.join('\n'));
await browser.close();
