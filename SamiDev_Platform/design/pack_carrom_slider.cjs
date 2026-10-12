// Pack the original generated oak rail into the existing atlas slot; physics unchanged.
const sharp=require('sharp'),path=require('node:path');
const root=path.join(__dirname,'..');
(async()=>{
 const rail=await sharp(path.join(__dirname,'original-assets/carrom-slider-oak.png')).trim().resize(1186,284,{fit:'fill'}).png().toBuffer();
 for(const rel of ['images/game.webp','images/themes/cat-atlas.webp']){
  const target=path.join(root,'game',rel);
  const atlas=await sharp(target).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  for(let y=1430;y<1714;y++)atlas.data.fill(0,(y*atlas.info.width+524)*4,(y*atlas.info.width+1710)*4);
  await sharp(atlas.data,{raw:atlas.info}).composite([{input:rail,left:524,top:1430}]).webp({lossless:true}).toFile(target+'.tmp');
  require('node:fs').renameSync(target+'.tmp',target);
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
