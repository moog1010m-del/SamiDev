/* Repack generated originals into runtime sprites without changing game geometry. */
const sharp=require('sharp'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),game=path.join(root,'game'),src=path.join(__dirname,'v36-originals');
async function write(buffer,rel){const file=path.join(game,rel);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,buffer);}
async function run(){
 const names={pool:'room-pool',carrom:'room-carrom',cards:'room-crazy8',football:'room-tablesoccer'};
 const tiles=[];const frames={};
 let index=0;
 for(const [name,source] of Object.entries(names)){
  const inner=await sharp(path.join(src,source+'.png')).trim().resize(224,224,{fit:'contain',background:'#00000000'}).png().toBuffer();
  const tile=await sharp(inner).extend({top:16,bottom:16,left:16,right:16,background:'#00000000'}).png().toBuffer();
  await write(tile,'room-sprites/'+name+'.png');
  tiles.push({input:tile,left:(index%2)*256,top:Math.floor(index/2)*256});
  frames[name]={x:(index%2)*256,y:Math.floor(index/2)*256,w:256,h:256};index++;
 }
 await write(await sharp({create:{width:512,height:512,channels:4,background:'#00000000'}}).composite(tiles).png().toBuffer(),'room-sprites/sprite-sheet.png');
 await write(Buffer.from(JSON.stringify({version:36,games:{pool:'pool.png',carrom:'carrom.png',crazy8:'cards.png',tablesoccer:'football.png'},spriteSheet:'sprite-sheet.png',frames},null,2)+'\n'),'room-sprites/manifest.json');
 const bg=path.join(src,'table-background.png');
 // Replace the floral pool surround and the existing shared table backdrops.
 for(const rel of ['images/table-background.webp','games/crazy8/images/table-background.webp','games/tablesoccer/images/table-background.webp','games/pool/images/imported/themes/th_basic_background.webp']){
  const target=path.join(game,rel);if(!fs.existsSync(target))continue;
  const {width,height}=await sharp(target).metadata();
  await write(await sharp(bg).resize(width,height,{fit:'fill'}).webp({quality:90}).toBuffer(),rel);
 }
 for(const style of ['classic','moon']){
  const source=path.join(src,'cue-'+style+'.png');
  // Generated sources point LEFT; the native 1020x30 cue frame points RIGHT.
  // Flip for both the table stick and strength control to keep the chalk at the ball.
  const cue=await sharp(source).trim().flop().resize(1020,30,{fit:'fill'}).webp({lossless:true}).toBuffer();
  await write(cue,'images/cues/'+style+'.webp');
  const preview=await sharp(cue).resize(680,20).png().toBuffer();
  await write(await sharp({create:{width:720,height:180,channels:4,background:'#20232d'}}).composite([{input:preview,left:20,top:80}]).webp({quality:94}).toBuffer(),'images/cues/'+style+'-preview.webp');
  if(style==='classic'){
   const atlas=path.join(game,'games/pool/images/ui/ui.webp');
   // Erase the old cue before overlaying its replacement (transparent tip edges).
   const {data,info}=await sharp(atlas).ensureAlpha().raw().toBuffer({resolveWithObject:true});
   for(let y=595;y<625;y++)for(let x=0;x<1020;x++)data.fill(0,(y*info.width+x)*4,(y*info.width+x)*4+4);
   const output=await sharp(data,{raw:info}).composite([{input:cue,left:0,top:595}]).webp({lossless:true}).toBuffer();
   await write(output,'games/pool/images/ui/ui.webp');
  }
 }
 console.log('V36: 4 room sprites + atlas, minimal backgrounds, classic and moon cues');
}
run().catch(e=>{console.error(e);process.exitCode=1});
