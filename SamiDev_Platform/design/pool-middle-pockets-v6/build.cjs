// Correct middle-pocket packing and pack its thin-rim insert; no renderer changes.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const sharp=require('C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const dir=__dirname,root=path.resolve(dir,'../..'),width=433,height=773;
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const clamp=n=>Math.max(0,Math.min(1,n));
const smooth=n=>{n=clamp(n);return n*n*(3-2*n);};
const map=(v,p)=>{for(let j=1;j<p.length;j++)if(v<=p[j][0]){const [a,b]=p[j-1],[c,d]=p[j];return b+(v-a)*(d-b)/(c-a);}return p.at(-1)[1];};
async function build(){
  const base=fs.readFileSync(path.join(dir,'backup/th_basic_table.webp'));
  const {data:old,info:oldInfo}=await sharp(base).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  if(oldInfo.width!==width||oldInfo.height!==height)throw Error('Quarter contract changed.');
  const {data:source,info}=await sharp(path.join(dir,'../pool-reference-v5/table-generated.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  if(info.width!==919||info.height!==1711)throw Error('Inspect source pocket coordinates before rebuilding.');
  const out=Buffer.from(old),xs=[[0,14],[16,30],[91,110],[433,459]];
  // The source circle is centered on row 781. The old seam sampled row 784.5.
  // Match both visible diameters, and land the mirror seam at the circle center.
  const sourceCenterY=781,pocketScaleY=.9;
  for(let y=690;y<height;y++)for(let x=0;x<145;x++){
    const amount=smooth((y-690)/30)*(1-smooth((x-110)/35));
    if(amount===0)continue;
    const sx=map(x+.5,xs)-.5,sy=sourceCenterY+(y+.5-height)/pocketScaleY;
    const x0=Math.floor(sx),y0=Math.floor(sy),fx=sx-x0,fy=sy-y0,i=(y*width+x)*4;
    const p=(xx,yy,c)=>{const k=(yy*info.width+xx)*4;return source[k+c]*source[k+3]/255;};
    for(let c=0;c<3;c++){
      const value=p(x0,y0,c)*(1-fx)*(1-fy)+p(x0+1,y0,c)*fx*(1-fy)+p(x0,y0+1,c)*(1-fx)*fy+p(x0+1,y0+1,c)*fx*fy;
      out[i+c]=Math.round(old[i+c]*(1-amount)+value*amount);
    }
  }
  // Remap the previous oversized lip to clean adjacent material, so its halo
  // cannot remain outside the smaller generated insert. This samples the same
  // generated metal/felt texture, without changing the rail or cushion outlines.
  const background=Buffer.from(out);
  for(let y=734;y<height;y++)for(let x=20;x<=97;x++){
    const dx=x-58.5,dy=y-772.5,distance=Math.hypot(dx,dy),amount=smooth((39-distance)/3);
    if(amount===0)continue;
    const sx=58.5+dx/distance*39,sy=772.5+dy/distance*39,x0=Math.floor(sx),y0=Math.min(height-2,Math.floor(sy)),fx=sx-x0,fy=sy-y0,i=(y*width+x)*4;
    for(let c=0;c<3;c++){
      const p=(xx,yy)=>background[(yy*width+xx)*4+c];
      const value=p(x0,y0)*(1-fx)*(1-fy)+p(x0+1,y0)*fx*(1-fy)+p(x0,y0+1)*(1-fx)*fy+p(x0+1,y0+1)*fx*fy;
      out[i+c]=Math.round(out[i+c]*(1-amount)+value*amount);
    }
  }
  // Pack only the generated circle and thin lip, centered on the mirror seam.
  const pocket=await sharp(path.join(dir,'pocket-art.png')).ensureAlpha().raw().toBuffer();
  for(let y=728;y<height;y++)for(let x=14;x<=103;x++){
    const distance=Math.hypot(x-58.5,y-772.5),amount=smooth((31.5-distance)/2);
    if(amount===0)continue;
    const px=817-y,py=x-14,k=(py*90+px)*4,i=(y*width+x)*4;
    for(let c=0;c<3;c++)out[i+c]=Math.round(out[i+c]*(1-amount)+pocket[k+c]*amount);
  }
  const quarter=await sharp(out,{raw:{width,height,channels:4}}).webp({lossless:true}).toBuffer();
  fs.writeFileSync(path.join(dir,'table.webp'),quarter);
  const q=sharp(quarter),pieces=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
  const full=await sharp({create:{width:width*2,height:height*2,channels:4,background:'#0000'}}).composite(pieces.map((input,i)=>({input,left:i%2*width,top:Math.floor(i/2)*height}))).png().toBuffer();
  fs.writeFileSync(path.join(dir,'table-portrait.png'),full);
  const landscape=await sharp(full).rotate(90).png().toBuffer();fs.writeFileSync(path.join(dir,'table-landscape.png'),landscape);
  await sharp(landscape).extract({left:690,top:0,width:166,height:150}).resize(498,450).png().toFile(path.join(dir,'middle-pocket-detail.png'));
  for(const [target,file,rotation] of [['game/games/pool/images/imported/themes/th_basic_preview.webp','basic-preview.webp',90],['game/images/themes/pool-midnight-preview.webp','midnight-preview.webp',0]]){
    const m=await sharp(fs.readFileSync(path.join(root,target))).metadata();await sharp(full).rotate(rotation).resize(m.width,m.height,{fit:'contain',background:rotation?'#13232a':'#0000'}).webp({lossless:true}).toFile(path.join(dir,file));
  }
  let changedPixels=0;
  const final=await sharp(quarter).ensureAlpha().raw().toBuffer();
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const i=(y*width+x)*4;if(final[i+3]!==old[i+3])throw Error('Alpha changed.');
    const changed=[0,1,2].some(c=>final[i+c]!==old[i+c]);
    if(changed&&(y<690||x>=145))throw Error('Pixels outside pocket crop changed.');
    if(changed)changedPixels++;
  }
  const before=JSON.parse(fs.readFileSync(path.join(dir,'before.json'),'utf8'));
  const fingerprints=Object.fromEntries(Object.entries(before.immutable).map(([p,h])=>[p,{before:h,after:hash(fs.readFileSync(path.join(root,p)))}]));
  if(Object.values(fingerprints).some(p=>p.before!==p.after))throw Error('Protected renderer, engine, or atlas changed.');
  const report={quarter:{width,height,sha256:hash(quarter)},changedPixels,alphaUnchanged:true,outsidePocketCropUnchanged:true,pocketCrop:{x:[0,145],y:[690,773]},sourceCenterY,pocketScaleY,fingerprints};
  fs.writeFileSync(path.join(dir,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({width,height,changedPixels,alphaUnchanged:true,outsidePocketCropUnchanged:true}));
  if(process.argv.includes('--install')){
    for(const [src,dst] of [['table.webp','game/games/pool/images/imported/themes/th_basic_table.webp'],['table.webp','game/images/themes/pool-midnight.webp'],['basic-preview.webp','game/games/pool/images/imported/themes/th_basic_preview.webp'],['midnight-preview.webp','game/images/themes/pool-midnight-preview.webp']])fs.copyFileSync(path.join(dir,src),path.join(root,dst));
    const runtime=path.join(root,'game/browser-runtime.js');let text=fs.readFileSync(runtime,'utf8');text=text.replace(/'pool-(?:reference-v5|middle-pockets-v6)-20261022'/,"'pool-middle-pockets-v6-20261022'");fs.writeFileSync(runtime,text);console.log('Installed middle-pocket crop correction.');
  }
}
build().catch(e=>{console.error(e);process.exit(1);});
