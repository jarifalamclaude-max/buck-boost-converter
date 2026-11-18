// Print HTML files to A4 PDFs with the pre-installed Playwright Chromium.
// usage: node print_pdf.js in1.html out1.pdf [in2.html out2.pdf ...]
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const a = process.argv.slice(2);
  for (let i = 0; i < a.length; i += 2) {
    await page.goto('file://' + path.resolve(a[i]), { waitUntil: 'load' });
    await page.pdf({ path: a[i + 1], format: 'A4', printBackground: true,
      margin: { top: '14mm', bottom: '16mm', left: '13mm', right: '13mm' },
      displayHeaderFooter: true, headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#666">SafeBuck-80 · <span class="pageNumber"></span>/<span class="totalPages"></span></div>' });
    console.log('pdf', a[i + 1]);
  }
  await browser.close();
})();
