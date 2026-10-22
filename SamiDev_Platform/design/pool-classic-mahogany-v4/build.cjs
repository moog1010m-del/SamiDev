// Pack generated raster artwork into the existing quarter-table texture contract.
// This does not paint new artwork or modify rendering/physics code.
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const sharp = require('C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const dir = __dirname;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
function map(value, points) {
  for (let i = 1; i < points.length; i++) if (value <= points[i][0]) {
    const [a,b] = points[i-1], [c,d] = points[i];
    return b + (value-a)*(d-b)/(c-a);
  }
  return points.at(-1)[1];
}
async function main() {
  const {data:src,info} = await sharp(path.join(dir,'table-generated.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const {data:mask} = await sharp(path.join(dir,'backup/th_basic_table.webp')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const width=433,height=773,out=Buffer.alloc(width*height*4);
  // Align the generated art's rail edges and pocket centers to the native sprite.
  // End the source at the center of its side pocket, the engine's mirror seam.
  const xs=[[0,0],[16,30],[60,137],[75,158],[83,182],[91,199],[131,280],[433,938]];
  const ys=[[0,0],[16,28],[75,155],[84,182],[91,199],[131,285],[725,1517],[773,1607]];
  for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
    const sx=Math.min(info.width-1,map(x+.5,xs)-.5), sy=Math.min(info.height-1,map(y+.5,ys)-.5);
    const x0=Math.max(0,Math.floor(sx)),y0=Math.max(0,Math.floor(sy)), x1=Math.min(info.width-1,x0+1),y1=Math.min(info.height-1,y0+1);
    const fx=sx-x0,fy=sy-y0,i=(y*width+x)*4;
    const sample=(px,py,c)=>{const k=(py*info.width+px)*4;return src[k+c]*src[k+3]/255;};
    for(let c=0;c<3;c++) out[i+c]=Math.round(
      sample(x0,y0,c)*(1-fx)*(1-fy)+sample(x1,y0,c)*fx*(1-fy)+
      sample(x0,y1,c)*(1-fx)*fy+sample(x1,y1,c)*fx*fy);
    // Retain only the original silhouette alpha; every RGB pixel is generated art.
    out[i+3]=mask[i+3];
  }
  const quarter=await sharp(out,{raw:{width,height,channels:4}}).webp({lossless:true}).toBuffer();
  fs.writeFileSync(path.join(dir,'table.webp'),quarter);
  const q=sharp(quarter),pieces=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
  const full=await sharp({create:{width:width*2,height:height*2,channels:4,background:'#0000'}}).composite(pieces.map((input,i)=>({input,left:(i%2)*width,top:Math.floor(i/2)*height}))).png().toBuffer();
  fs.writeFileSync(path.join(dir,'table-portrait.png'),full);
  await sharp(full).rotate(90).png().toFile(path.join(dir,'table-landscape.png'));
  // Store thumbnails show the complete table rather than stretching a quarter.
  const root=path.resolve(dir,'../..');
  for(const [target,file] of [['game/games/pool/images/imported/themes/th_basic_preview.webp','basic-preview.webp'],['game/images/themes/pool-midnight-preview.webp','midnight-preview.webp']]) {
    const m=await sharp(path.join(root,target)).metadata();
    const landscape=file==='basic-preview.webp';
    await sharp(full).rotate(landscape?90:0).resize(m.width,m.height,{fit:'contain',background:landscape?'#13232a':'#0000'}).webp({lossless:true}).toFile(path.join(dir,file));
  }
  const report={width,height,format:'lossless WebP',construction:'Native quarter sprite mirrored four times; no engine or UI-atlas edits',source:{width:info.width,height:info.height},alphaMaskUnchanged:true,sha256:hash(quarter),sourceMapping:{x:xs,y:ys}};
  fs.writeFileSync(path.join(dir,'build-report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
}
main().catch(error=>{console.error(error);process.exit(1);});
