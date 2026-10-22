// Atlas packing of newly generated Plazr materials; no previous table pixels read.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const deps='C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/';
const sharp=require(deps+'sharp'),{createCanvas}=require(deps+'@napi-rs/canvas');
const dir=__dirname,root=path.resolve(dir,'../..'),W=433,H=773;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t)};
function map(v,p){for(let i=1;i<p.length;i++)if(v<=p[i][0]){const[a,b]=p[i-1],[c,d]=p[i];return b+(v-a)*(d-b)/(c-a)}return p.at(-1)[1]}
async function build(){
 const {data:src,info}=await sharp(path.join(dir,'quarter-generated.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const pixels=Buffer.alloc(W*H*4),xMap=[[0,0],[16,42],[60,158],[76,195],[92,235],[132,340],[146,375],[433,928]],yMap=[[0,0],[15,53],[60,174],[76,220],[92,246],[131,342],[146,375],[729,1480],[733,1504],[773,1608]];
 const sideMap=[[0,0],[16,42],[25,100],[59,198],[81,222],[92,235],[433,928]];
 function sample(x,y,c){x=Math.max(0,Math.min(info.width-2,x));y=Math.max(0,Math.min(info.height-2,y));const ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy,p=(a,b)=>src[(b*info.width+a)*4+c];return p(ix,iy)*(1-fx)*(1-fy)+p(ix+1,iy)*fx*(1-fy)+p(ix,iy+1)*(1-fx)*fy+p(ix+1,iy+1)*fx*fy;}
 for(let y=0;y<H;y++)for(let x=0;x<W;x++){
  const i=(y*W+x)*4;
  // Native silhouette authored from geometry, never copied from another asset.
  let coverage=Math.min(1,Math.max(0,x-15.5),Math.max(0,y-14.5));
  if(x<80&&y<79)coverage=Math.min(coverage,Math.max(0,Math.min(1,64.5-Math.hypot(x-80,y-79))));
  if(!coverage)continue;
  const t=smooth((y-733)/40),sx=map(x,xMap)*(1-t)+map(x,sideMap)*t,sy=map(y,yMap);
  for(let c=0;c<3;c++)pixels[i+c]=Math.round(sample(sx,sy,c));pixels[i+3]=Math.round(sample(sx,sy,3)*coverage);
 }
 const quarter=await sharp(pixels,{raw:{width:W,height:H,channels:4}}).webp({lossless:true}).toBuffer();fs.writeFileSync(path.join(dir,'table.webp'),quarter);
 // This crop contains the new generated metal inlay only; transparent border retained.
 const engraving=await sharp(path.join(dir,'engraving-generated.png')).extract({left:49,top:265,width:2075,height:198}).resize(1100,105).webp({lossless:true}).toBuffer();fs.writeFileSync(path.join(dir,'engraving.webp'),engraving);
 const q=sharp(quarter),parts=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
 let full=await sharp({create:{width:W*2,height:H*2,channels:4,background:'#0000'}}).composite(parts.map((input,i)=>({input,left:i%2*W,top:Math.floor(i/2)*H}))).png().toBuffer();
 const mark=await sharp(engraving).resize(480,44).png().toBuffer();full=await sharp(full).composite([{input:mark,left:193,top:16}]).png().toBuffer();fs.writeFileSync(path.join(dir,'table-portrait.png'),full);await sharp(full).rotate(90).png().toFile(path.join(dir,'table-landscape.png'));
 // Native backgrounds tile. A flat matte tone avoids a repeated vignette grid.
 const background=createCanvas(128,128),ctx=background.getContext('2d');ctx.fillStyle='#13212b';ctx.fillRect(0,0,128,128);await sharp(background.toBuffer('image/png')).webp({lossless:true}).toFile(path.join(dir,'background.webp'));
 await sharp(full).rotate(90).resize(512,326,{fit:'contain',background:'#111e27'}).webp({lossless:true}).toFile(path.join(dir,'basic-preview.webp'));
 await sharp(full).resize(224,400,{fit:'contain',background:'#0000'}).webp({lossless:true}).toFile(path.join(dir,'midnight-preview.webp'));
 const before=JSON.parse(fs.readFileSync(path.join(dir,'before.json'))),protectedPaths=Object.keys(before).filter(p=>p.startsWith('game/images/pool-large/')||p==='game/games/pool/main.js'||p==='game/games/pool/images/ui/ui.webp');
 const fingerprints={};for(const p of protectedPaths){const after=hash(fs.readFileSync(path.join(root,p)));if(after!==before[p].sha256)throw Error('Protected mode/engine/atlas changed: '+p);fingerprints[p]={before:before[p].sha256,after};}
 fs.writeFileSync(path.join(dir,'asset-verification.json'),JSON.stringify({quarter:{width:W,height:H,sha256:hash(quarter)},generatedSourcesOnly:true,generatedAlphaResampled:true,nativeSilhouetteAuthored:true,oldTablePixelsRead:false,engravingMirrored:false,nativeMarkRect:{x:193,y:16,width:480,height:44},fingerprints},null,2)+'\n');
 if(process.argv.includes('--install')){
  for(const [s,d] of [['table.webp','game/games/pool/images/imported/themes/th_basic_table.webp'],['table.webp','game/images/themes/pool-midnight.webp'],['background.webp','game/games/pool/images/imported/themes/th_basic_background.webp'],['basic-preview.webp','game/games/pool/images/imported/themes/th_basic_preview.webp'],['midnight-preview.webp','game/images/themes/pool-midnight-preview.webp'],['engraving.webp','game/images/themes/plazr-engraving.webp']])fs.copyFileSync(path.join(dir,s),path.join(root,d));
 }
 console.log(JSON.stringify({ok:true,quarter:[W,H],newSourcesOnly:true,nativeEngineAndLargeModeUnchanged:true}));
}
build().catch(e=>{console.error(e);process.exit(1)});
