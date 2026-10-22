// Fit the cleaned reference-style raster to the existing quarter-sprite contract.
// No engine changes, new draw calls, or new atlas coordinates.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const sharp=require('C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const dir=__dirname,root=path.resolve(dir,'../..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const map=(v,p)=>{for(let j=1;j<p.length;j++)if(v<=p[j][0]){const [a,b]=p[j-1],[c,d]=p[j];return b+(v-a)*(d-b)/(c-a);}return p.at(-1)[1];};
async function build(){
  const {data:source,info}=await sharp(path.join(dir,'table-generated.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  if(info.width!==919||info.height!==1711)throw Error('Source size changed; inspect and realign before packing.');
  const {data:old}=await sharp(path.join(dir,'backup/th_basic_table.webp')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const width=433,height=773,out=Buffer.alloc(width*height*4);
  // Keep the native cloth boundaries, margin, center seams and texture dimensions.
  // Crop at the actual side-pocket center, not the bottom of the source image.
  const xs=[[0,14],[16,30],[91,110],[433,459]],ys=[[0,11],[16,27],[91,102],[773,785]];
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const sx=map(x+.5,xs)-.5,sy=map(y+.5,ys)-.5,x0=Math.floor(sx),y0=Math.floor(sy),fx=sx-x0,fy=sy-y0,i=(y*width+x)*4;
    const p=(xx,yy,c)=>{const n=(yy*info.width+xx)*4;return source[n+c]*source[n+3]/255;};
    for(let c=0;c<3;c++)out[i+c]=Math.round(p(x0,y0,c)*(1-fx)*(1-fy)+p(x0+1,y0,c)*fx*(1-fy)+p(x0,y0+1,c)*(1-fx)*fy+p(x0+1,y0+1,c)*fx*fy);
    out[i+3]=old[i+3];
  }
  const quarter=await sharp(out,{raw:{width,height,channels:4}}).webp({lossless:true}).toBuffer();
  fs.writeFileSync(path.join(dir,'table.webp'),quarter);
  const q=sharp(quarter),pieces=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
  const portrait=await sharp({create:{width:width*2,height:height*2,channels:4,background:'#0000'}}).composite(pieces.map((input,i)=>({input,left:i%2*width,top:Math.floor(i/2)*height}))).png().toBuffer();
  fs.writeFileSync(path.join(dir,'table-portrait.png'),portrait);
  await sharp(portrait).rotate(90).png().toFile(path.join(dir,'table-landscape.png'));
  for(const [target,filename,rotation] of [['game/games/pool/images/imported/themes/th_basic_preview.webp','basic-preview.webp',90],['game/images/themes/pool-midnight-preview.webp','midnight-preview.webp',0]]){
    const m=await sharp(fs.readFileSync(path.join(root,target))).metadata();
    await sharp(portrait).rotate(rotation).resize(m.width,m.height,{fit:'contain',background:rotation?'#13232a':'#0000'}).webp({lossless:true}).toFile(path.join(dir,filename));
  }
  const baseline=JSON.parse(fs.readFileSync(path.join(dir,'before.json'),'utf8'));
  const fingerprints=Object.fromEntries(Object.entries(baseline.immutable).map(([p,h])=>[p,{before:h,after:sha(fs.readFileSync(path.join(root,p)))}]));
  if(Object.values(fingerprints).some(p=>p.before!==p.after))throw Error('Protected source or UI-atlas changed.');
  const {data:final}=await sharp(quarter).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  for(let i=3;i<final.length;i+=4)if(final[i]!==old[i])throw Error('Native silhouette alpha changed.');
  fs.writeFileSync(path.join(dir,'verification.json'),JSON.stringify({quarter:{width,height,format:'lossless WebP',sha256:sha(quarter)},source:{width:info.width,height:info.height},alphaUnchanged:true,engineAndAtlasUnchanged:true,fingerprints,sourceMapping:{x:xs,y:ys}},null,2)+'\n');
  console.log('Packed 433x773; native alpha, engine and UI atlas unchanged.');
  if(process.argv.includes('--install')){
    for(const [src,dest] of [['table.webp','game/games/pool/images/imported/themes/th_basic_table.webp'],['table.webp','game/images/themes/pool-midnight.webp'],['basic-preview.webp','game/games/pool/images/imported/themes/th_basic_preview.webp'],['midnight-preview.webp','game/images/themes/pool-midnight-preview.webp']])fs.copyFileSync(path.join(dir,src),path.join(root,dest));
    const runtime=path.join(root,'game/browser-runtime.js');let text=fs.readFileSync(runtime,'utf8');
    text=text.replace(/'pool-(?:mahogany-v4|reference-v5)-20261022'/,"'pool-reference-v5-20261022'");fs.writeFileSync(runtime,text);
    console.log('Installed table and matching previews.');
  }
}
build().catch(error=>{console.error(error);process.exit(1);});
