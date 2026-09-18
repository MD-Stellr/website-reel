// Deterministic frame-by-frame capture of a website with a scripted scroll.
// JS time (rAF, timers, performance.now) is driven by Playwright's fake clock;
// CSS/WAAPI animations are frozen on the document timeline and stepped manually;
// <video> elements are seeked per frame. Result: every frame is a crisp,
// full-resolution screenshot and all motion plays at true speed.
//
// usage: node capture.mjs <config.json>
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const {
  url, out, width, height, dpr = 2, fps = 30, duration,
  settleMs = 5000, keyframes, hideSelectors = [], css = '', format = 'jpeg', quality = 95,
  startFrame = 0, endFrame,
} = cfg;

fs.mkdirSync(out, { recursive: true });
const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; // easeInOutCubic

// keyframes: [[timeSec, scrollY], ...]; equal consecutive y = hold.
// interp "ease" (default) comes to rest at every keyframe; "smooth" passes through them without stopping
// (monotone cubic / Fritsch-Carlson, so velocity is continuous and the scroll never overshoots or reverses).
const tangents = (() => {
  const n = keyframes.length, d = [], m = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((keyframes[i + 1][1] - keyframes[i][1]) / (keyframes[i + 1][0] - keyframes[i][0]));
  m[0] = d[0] ?? 0; m[n - 1] = d[n - 2] ?? 0;
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : 2 / (1 / d[i - 1] + 1 / d[i]);
  return m;
})();
function scrollAt(t) {
  if (cfg.interp === 'smooth') {
    if (t <= keyframes[0][0]) return keyframes[0][1];
    for (let i = 1; i < keyframes.length; i++) {
      const [t1, y1] = keyframes[i], [t0, y0] = keyframes[i - 1];
      if (t > t1) continue;
      const h = t1 - t0, s = (t - t0) / h, s2 = s * s, s3 = s2 * s;
      return (2 * s3 - 3 * s2 + 1) * y0 + (s3 - 2 * s2 + s) * h * tangents[i - 1]
        + (-2 * s3 + 3 * s2) * y1 + (s3 - s2) * h * tangents[i];
    }
    return keyframes[keyframes.length - 1][1];
  }
  if (t <= keyframes[0][0]) return keyframes[0][1];
  for (let i = 1; i < keyframes.length; i++) {
    const [t1, y1] = keyframes[i];
    const [t0, y0] = keyframes[i - 1];
    if (t <= t1) return y0 + (y1 - y0) * ease((t - t0) / (t1 - t0));
  }
  return keyframes[keyframes.length - 1][1];
}

const browser = await chromium.launch({
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars', '--force-color-profile=srgb'],
});
const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr });
const page = await context.newPage();
// keep a real timer around for timeouts while the fake clock is paused
await context.addInitScript(() => { window.__realSetTimeout = window.setTimeout.bind(window); });
await page.clock.install();
await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 });

// Load lazy media up front without scrolling (scrolling would pre-trigger reveal animations).
await page.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; }));
await page.waitForLoadState('networkidle');
await page.evaluate(() => Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))));
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(settleMs); // preloader / intro plays out in real time

await page.addStyleTag({ content: `${hideSelectors.join(',') || '#__none'}{display:none!important} html{scrollbar-width:none} ${css}` });

// Freeze the document timeline so CSS/WAAPI animations only advance when we step them.
const cdp = await context.newCDPSession(page);
await cdp.send('Animation.enable');
await cdp.send('Animation.setPlaybackRate', { playbackRate: 0 });
await page.clock.pauseAt(await page.evaluate(() => Date.now() + 100));

await page.evaluate(() => {
  const recs = new WeakMap();
  window.__vtStep = async (t) => {
    for (const a of document.getAnimations()) {
      if (a.timeline !== document.timeline) continue; // scroll-driven timelines follow scroll
      if (a.playState === 'paused' || a.playState === 'idle') continue;
      let r = recs.get(a);
      if (!r) { r = { t0: t, c0: a.currentTime ?? 0 }; recs.set(a, r); }
      a.currentTime = r.c0 + (t - r.t0) * a.playbackRate;
    }
    const seeks = [];
    for (const v of document.querySelectorAll('video')) {
      if (!v.duration || !isFinite(v.duration)) continue;
      if (v.__t0 === undefined) { v.__t0 = t; v.__c0 = v.currentTime; }
      v.pause();
      const target = (v.__c0 + (t - v.__t0) / 1000) % v.duration;
      seeks.push(new Promise(res => { v.addEventListener('seeked', res, { once: true }); v.currentTime = target; }));
    }
    await Promise.race([Promise.all(seeks), new Promise(r => window.__realSetTimeout(r, 3000))]);
  };
});

const total = endFrame ?? Math.round(duration * fps);
const frameMs = 1000 / fps;
const started = Date.now();
await page.evaluate(y => { window.scrollTo({ top: y, behavior: 'instant' }); }, scrollAt(0));

for (let f = 0; f < total; f++) {
  const t = f / fps;
  const y = Math.round(scrollAt(t) * dpr) / dpr;
  await page.evaluate(y => {
    window.scrollTo({ top: y, behavior: 'instant' });
    document.dispatchEvent(new Event('scroll', { bubbles: true })); // notify listeners now, not at next real frame
  }, y);
  await page.clock.runFor(frameMs);
  await page.evaluate(t => window.__vtStep(t), f * frameMs);
  if (f >= startFrame) {
    const file = path.join(out, `f${String(f).padStart(5, '0')}.${format === 'png' ? 'png' : 'jpg'}`);
    await page.screenshot({ path: file, type: format, ...(format === 'jpeg' ? { quality } : {}), animations: 'allow', caret: 'hide' });
  }
  if (f % 30 === 0) console.log(`frame ${f}/${total}  y=${y.toFixed(0)}  ${((Date.now() - started) / (f + 1)).toFixed(0)}ms/frame`);
}
console.log(`done: ${total} frames in ${((Date.now() - started) / 1000).toFixed(1)}s -> ${out}`);
await browser.close();
