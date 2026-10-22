// Fit generated materials to the original sprite's pixel geometry.
const sharp = require(process.env.PLAZR_SHARP_MODULE || 'C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const dir = __dirname;
const root = path.resolve(dir, '../..');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
async function main() {
 const originalPath = path.join(dir, 'original-quarter.webp');
 const {data: original, info} = await sharp(originalPath).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const {width:w,height:h} = info;
 if(w!==433 || h!==773) throw Error('Unexpected original sprite size');
 const generated = await sharp(path.join(dir,'generated-material.png')).resize(w,h,{fit:'fill'}).removeAlpha().raw().toBuffer();
 const out=Buffer.from(original);
 let pocketPixels=0;
 for(let p=0;p<w*h;p++) {
  const i=p*4,j=p*3,r=original[i],g=original[i+1],b=original[i+2];
  // Original alpha, black pocket interiors and silhouette are immutable.
  if(!original[i+3] || Math.max(r,g,b)<24) {pocketPixels++;continue;}
  const felt=b>r*1.2 && g>r*1.15;
  if(felt) {
   // Material membership and shading come from the original, not generated edges.
   const l=.2126*r+.7152*g+.0722*b;
   const texture=(generated[j+1]/255-.35)*7;
   out[i]=Math.max(0,Math.min(255,l*.27+texture));
   out[i+1]=Math.max(0,Math.min(255,l*1.12+texture));
   out[i+2]=Math.max(0,Math.min(255,l*.62+texture));
  } else {
   // Retain bevels and highlights while borrowing the generated mahogany material.
   for(let c=0;c<3;c++) out[i+c]=Math.round(original[i+c]*.70+generated[j+c]*.30);
  }
 }
 const output=await sharp(out,{raw:{width:w,height:h,channels:4}}).webp({lossless:true}).toBuffer();
 fs.writeFileSync(path.join(dir,'classic-green-quarter.webp'),output);
 const decoded=await sharp(output).ensureAlpha().raw().toBuffer();
 for(let p=0;p<w*h;p++) {
  const i=p*4;
  if(decoded[i+3]!==original[i+3]) throw Error('Alpha geometry changed');
  if(Math.max(original[i],original[i+1],original[i+2])<24 && !decoded.subarray(i,i+4).equals(original.subarray(i,i+4))) throw Error('Pocket mask changed');
 }
 async function preview(bytes,name) {
  const q=sharp(bytes);
  const a=await q.clone().png().toBuffer();
  const b=await q.clone().flop().png().toBuffer();
  const c=await q.clone().flip().png().toBuffer();
  const d=await q.clone().flip().flop().png().toBuffer();
  const full=await sharp({create:{width:w*2,height:h*2,channels:4,background:'#0c1210'}}).composite([{input:a,left:0,top:0},{input:b,left:w,top:0},{input:c,left:0,top:h},{input:d,left:w,top:h}]).png().toBuffer();
  await sharp(full).rotate(90).resize({width:1200}).png().toFile(path.join(dir,name));
 }
 await preview(fs.readFileSync(originalPath),'before.png');
 await preview(output,'after.png');
 const protectedPaths=['game/games/pool/main.js','game/browser-runtime.js','game/pool-presentation.js'];
 const protectedHashes=Object.fromEntries(protectedPaths.map(p=>[p,hash(fs.readFileSync(path.join(root,p)))]));
 fs.writeFileSync(path.join(dir,'validation.json'),JSON.stringify({width:w,height:h,alphaUnchanged:true,pocketPixelsUnchanged:true,pocketPixels,originalSha256:hash(fs.readFileSync(originalPath)),replacementSha256:hash(output),protectedHashes},null,2)+'\n');
 console.log(JSON.stringify({width:w,height:h,alphaUnchanged:true,pocketPixelsUnchanged:true}));
}
main().catch(e=>{console.error(e.message);process.exit(1)});
