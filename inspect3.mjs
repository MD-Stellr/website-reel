import { chromium } from 'playwright';
const url = process.argv[2];
const browser = await chromium.launch({ args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const reqs = [];
page.on('request', r => reqs.push({ url: r.url(), type: r.resourceType() }));
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(4000);
const info = await page.evaluate(() => {
  const c = document.querySelector('canvas');
  const sticky = [...document.querySelectorAll('div')].find(d => d.className.includes('sticky top-0 h-[100svh]'));
  const wrap = sticky?.parentElement;
  const r = wrap?.getBoundingClientRect();
  return {
    canvas: c && { w: c.width, h: c.height, cssW: c.clientWidth, cssH: c.clientHeight, parentCls: c.parentElement.className.slice(0, 100) },
    heroWrap: r && { top: r.top + scrollY, h: r.height, cls: wrap.className.slice(0, 100) },
    sections: [...document.querySelectorAll('section, h1, h2')].map(e => { const b = e.getBoundingClientRect(); return `${e.tagName} top=${Math.round(b.top + scrollY)} h=${Math.round(b.height)} ${(e.innerText || '').replace(/\s+/g, ' ').slice(0, 60)}`; }),
  };
});
console.log(JSON.stringify(info.canvas), JSON.stringify(info.heroWrap));
console.log(info.sections.join('\n'));
const imgs = reqs.filter(r => r.type === 'image' || /\.(jpe?g|webp|avif|png)(\?|$)/.test(r.url));
console.log('image requests at load:', imgs.length);
const byDir = {}; for (const r of imgs) { const k = r.url.replace(/[^/]+$/, ''); byDir[k] = (byDir[k] || 0) + 1; }
console.log(Object.entries(byDir).sort((a, b) => b[1] - a[1]).slice(0, 6));
console.log(imgs.slice(0, 3).map(r => r.url));
// scroll into the hero and see whether more frames get requested
const before = reqs.length;
for (let y = 0; y <= (info.heroWrap?.h || 3000); y += 200) { await page.evaluate(y => scrollTo(0, y), y); await page.waitForTimeout(80); }
await page.waitForTimeout(1500);
console.log('extra requests while scrolling hero:', reqs.length - before);
await browser.close();
