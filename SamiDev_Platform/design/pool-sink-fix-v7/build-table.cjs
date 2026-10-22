// Refit existing generated cushion material to the actual native jaw outlines.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const sharp=require('C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const dir=__dirname,root=path.resolve(dir,'../..'),width=433,height=773;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const smooth=v=>{v=Math.max(0,Math.min(1,v));return v*v*(3-2*v)};
async function build(){
  const {data:src}=await sharp(path.join(dir,'backup/th_basic_table.webp')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const out=Buffer.from(src);
  const sample=(x,y,c)=>{
    const x0=Math.floor(x),y0=Math.floor(y),fx=x-x0,fy=y-y0,p=(xx,yy)=>src[(yy*width+xx)*4+c];
    return p(x0,y0)*(1-fx)*(1-fy)+p(x0+1,y0)*fx*(1-fy)+p(x0,y0+1)*(1-fx)*fy+p(x0+1,y0+1)*fx*fy;
  };
  // Clear the previous toe's cast edge as well, while protecting the round lip.
  for(let y=58;y<=102;y++)for(let x=98;x<=149;x++){
    const oldStart=108+(y-60)*30/32,newStart=y<=76?132:132+(Math.min(92,y)-76)*14/16;
    const amount=smooth((x-oldStart+10)/7)*(1-smooth((x-newStart)/3))*smooth((y-58)/2)*(1-smooth((y-97)/5))*smooth((Math.hypot(x-80,y-81)-33)/3),i=(y*width+x)*4;
    for(let c=0;c<3;c++)out[i+c]=Math.round(out[i+c]*(1-amount)+sample(x+50,y+70,c)*amount);
  }
  for(let x=60;x<=102;x++)for(let y=98;y<=149;y++){
    const oldStart=108+(x-63)*30/29,newStart=x<=76?131:131+(Math.min(92,x)-76)*15/16;
    const amount=smooth((y-oldStart+10)/7)*(1-smooth((y-newStart)/3))*smooth((x-60)/3)*(1-smooth((x-97)/5))*smooth((Math.hypot(x-80,y-81)-33)/3),i=(y*width+x)*4;
    for(let c=0;c<3;c++)out[i+c]=Math.round(out[i+c]*(1-amount)+sample(x+70,y+50,c)*amount);
  }
  // The top native rail begins at (132,15), bevels from (132,76) to (146,92).
  for(let y=59;y<=94;y++){
    const oldStart=108+(y-60)*30/32,newStart=y<=76?132:132+(Math.min(92,y)-76)*14/16,edge=smooth((y-59)/2)*(1-smooth((y-92)/3));
    for(let x=Math.floor(oldStart-3);x<=200;x++){
      const amount=edge*(x<newStart?smooth((x-(oldStart-3))/3):1),i=(y*width+x)*4;
      const sx=x<newStart?x+50:oldStart+(x-newStart)*(200-oldStart)/(200-newStart),sy=x<newStart?y+70:y;
      for(let c=0;c<3;c++)out[i+c]=Math.round(out[i+c]*(1-amount)+sample(sx,sy,c)*amount);
    }
  }
  // The left native rail begins at (16,131), bevels from (76,131) to (92,146).
  for(let x=62;x<=94;x++){
    const oldStart=108+(x-63)*30/29,newStart=x<=76?131:131+(Math.min(92,x)-76)*15/16,edge=smooth((x-62)/2)*(1-smooth((x-92)/3));
    for(let y=Math.floor(oldStart-3);y<=200;y++){
      const amount=edge*(y<newStart?smooth((y-(oldStart-3))/3):1),i=(y*width+x)*4;
      const sx=y<newStart?x+70:x,sy=y<newStart?y+50:oldStart+(y-newStart)*(200-oldStart)/(200-newStart);
      for(let c=0;c<3;c++)out[i+c]=Math.round(out[i+c]*(1-amount)+sample(sx,sy,c)*amount);
    }
  }
  const quarter=await sharp(out,{raw:{width,height,channels:4}}).webp({lossless:true}).toBuffer();fs.writeFileSync(path.join(dir,'table.webp'),quarter);
  const q=sharp(quarter),parts=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
  const full=await sharp({create:{width:width*2,height:height*2,channels:4,background:'#0000'}}).composite(parts.map((input,i)=>({input,left:i%2*width,top:Math.floor(i/2)*height}))).png().toBuffer();
  fs.writeFileSync(path.join(dir,'table-portrait.png'),full);await sharp(full).rotate(90).png().toFile(path.join(dir,'table-landscape.png'));
  await sharp(quarter).extract({left:0,top:0,width:190,height:190}).resize(760,760).png().toFile(path.join(dir,'corner-after.png'));
  for(const [target,file,rotation] of [['game/games/pool/images/imported/themes/th_basic_preview.webp','basic-preview.webp',90],['game/images/themes/pool-midnight-preview.webp','midnight-preview.webp',0]]){
    const m=await sharp(fs.readFileSync(path.join(root,target))).metadata();await sharp(full).rotate(rotation).resize(m.width,m.height,{fit:'contain',background:rotation?'#13232a':'#0000'}).webp({lossless:true}).toFile(path.join(dir,file));
  }
  const final=await sharp(quarter).ensureAlpha().raw().toBuffer();let changed=0;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const i=(y*width+x)*4;if(final[i+3]!==src[i+3])throw Error('Alpha changed');
    if([0,1,2].some(c=>final[i+c]!==src[i+c])){changed++;if(x>200||y>200)throw Error('Pixels changed outside corner');}
  }
  const baseline=JSON.parse(fs.readFileSync(path.join(dir,'before.json'))),fingerprints={};
  for(const [p,before] of Object.entries(baseline.immutable)){const after=hash(fs.readFileSync(path.join(root,p)));if(before!==after)throw Error('Native engine/UI atlas changed: '+p);fingerprints[p]={before,after};}
  fs.writeFileSync(path.join(dir,'table-verification.json'),JSON.stringify({quarter:{width,height,sha256:hash(quarter)},changedPixels:changed,alphaUnchanged:true,onlyCornerChanged:true,midPocketsUnchanged:true,fingerprints},null,2)+'\n');
  console.log('Refit corner material to native jaws; preserved alpha, middle pockets and native engine.');
  if(process.argv.includes('--install')){
    for(const [src,dst] of [['table.webp','game/games/pool/images/imported/themes/th_basic_table.webp'],['table.webp','game/images/themes/pool-midnight.webp'],['basic-preview.webp','game/games/pool/images/imported/themes/th_basic_preview.webp'],['midnight-preview.webp','game/images/themes/pool-midnight-preview.webp']])fs.copyFileSync(path.join(dir,src),path.join(root,dst));
    const runtime=path.join(root,'game/browser-runtime.js');let s=fs.readFileSync(runtime,'utf8');s=s.replace(/'pool-(?:middle-pockets-v6|sink-fix-v7)-20261022'/,"'pool-sink-fix-v7-20261022'");fs.writeFileSync(runtime,s);
  }
}
build().catch(e=>{console.error(e);process.exit(1)});
