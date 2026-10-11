// Rasterize the original SVG source for Flutter's built-in Image.asset widget.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../game/platform/assets/ranks');
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
try{
  const page=await browser.newPage({viewport:{width:160,height:160},deviceScaleFactor:2});
  for(let i=1;i<=100;i++){
    const base=`level-${String(i).padStart(3,'0')}`;
    await page.setContent(`<style>body{margin:0;background:transparent}svg{display:block}</style>${fs.readFileSync(path.join(root,base+'.svg'),'utf8')}`);
    await page.locator('svg').screenshot({path:path.join(root,base+'.png'),omitBackground:true});
  }
}finally{await browser.close();}
console.log('Rendered 100 original badges for native profiles');
