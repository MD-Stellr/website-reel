import { chromium } from 'playwright';
const url = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 810 }, deviceScaleFactor: 1 });
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const info = await page.evaluate(() => {
  const libs = {
    gsap: !!window.gsap, ScrollTrigger: !!window.ScrollTrigger, lenis: !!document.querySelector('.lenis, html.lenis') || !!window.lenis,
    next: !!window.__NEXT_DATA__ || !!document.querySelector('script[src*="_next"]'),
    three: !!window.THREE, canvas: document.querySelectorAll('canvas').length, video: document.querySelectorAll('video').length,
    iframes: document.querySelectorAll('iframe').length,
  };
  const fixed = [...document.querySelectorAll('body *')].filter(e => ['fixed','sticky'].includes(getComputedStyle(e).position))
    .map(e => ({ tag: e.tagName, cls: (e.className+'').slice(0,80), pos: getComputedStyle(e).position, h: e.getBoundingClientRect().height|0, w: e.getBoundingClientRect().width|0 }));
  const links = [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => h.startsWith(location.origin)))];
  const hidden = [...document.querySelectorAll('body *')].filter(e => getComputedStyle(e).opacity === '0').length;
  return { title: document.title, height: document.documentElement.scrollHeight, libs, fixed, links, anims: document.getAnimations().length, opacity0: hidden,
    htmlClass: document.documentElement.className, bodyClass: document.body.className, fonts: [...new Set([...document.querySelectorAll('body *')].slice(0,300).map(e=>getComputedStyle(e).fontFamily))].slice(0,6) };
});
console.log(JSON.stringify(info, null, 2));
await page.screenshot({ path: 'inspect-top.png' });
await browser.close();
