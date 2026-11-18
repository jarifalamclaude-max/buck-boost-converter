// usage: node svg2png.js in.svg out.png [width]   (white background, for the docs)
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const w = parseInt(process.argv[4] || '1400');
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: w, height: 1000 }, deviceScaleFactor: 1 });
  await p.setContent(`<html><body style="margin:0;background:#fff">${fs.readFileSync(process.argv[2], 'utf8')}</body></html>`);
  await p.evaluate((w) => { const s = document.querySelector('svg'); s.setAttribute('width', String(w)); s.removeAttribute('height'); }, w);
  await (await p.$('svg')).screenshot({ path: process.argv[3] }); await b.close();
})();
