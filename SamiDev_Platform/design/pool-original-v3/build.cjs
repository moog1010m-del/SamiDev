// Original raster artwork. No SVG and no pixels sampled from previous game art.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const deps='C:/Users/Dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/';
const sharp=require(deps+'sharp'),{createCanvas,loadImage}=require(deps+'@napi-rs/canvas');
const dir=__dirname,root=path.resolve(dir,'../..');
const layout=JSON.parse(fs.readFileSync(path.join(dir,'atlas-layout.json')));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const C={teal:'#30d9cf',ink:'#0b1820',silver:'#b8cbd0',white:'#f4f5e9',copper:'#cf906b'};
function circle(c,x,y,r,fill){c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=fill;c.fill();}
function line(c,pts,color,width=3){c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.lineJoin='round';c.beginPath();pts.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.stroke();}
function round(c,x,y,w,h,r,fill){c.fillStyle=fill;c.beginPath();c.roundRect(x,y,w,h,r);c.fill();}
function native(name,w,h){
 const a=createCanvas(w*4,h*4),c=a.getContext('2d');c.scale(4,4);
 const X=w/2,Y=h/2,R=Math.min(w,h)*.43;
 if(/^ball\d+$/.test(name)){
  const n=+name.slice(4),colors=['#f3f1e4','#e5b62c','#285cb9','#df423b','#7044a4','#ed7b31','#28784c','#8c344b','#13212a'];
  c.fillStyle=n>=9?'#f1f2e8':colors[n];c.fillRect(0,0,w,h);
  if(n>=9){c.fillStyle=colors[n-8];c.fillRect(0,h*.22,w,h*.56);}
  if(n){circle(c,X,Y,h*.225,'#fcfcf3');c.fillStyle='#17252b';c.font=`bold ${h*.35}px Arial`;c.textAlign='center';c.textBaseline='middle';c.fillText(String(n),X,Y+1);}
 }else if(name==='ball_shadow'||name==='hilite'||name==='valid_ball_highlight'){
  const g=c.createRadialGradient(X,Y,0,X,Y,R);g.addColorStop(0,name==='ball_shadow'?'#000b': '#a3fff3aa');g.addColorStop(1,'#0000');circle(c,X,Y,R,g);
 }else if(name==='dot'||name==='ball_collected'){circle(c,X,Y,R,C.teal);circle(c,X-R*.2,Y-R*.25,R*.3,'#fff9');
 }else if(name==='btn_angle_icon'){line(c,[[w*.18,h*.72],[X,h*.25],[w*.82,h*.72]],C.white,Math.max(2,h*.1));
 }else if(name==='preset_highlight'){round(c,2,2,w-4,h-4,Math.min(w,h)*.18,'#1c636b55');c.strokeStyle=C.teal;c.lineWidth=3;c.strokeRect(6,6,w-12,h-12);
 }else if(name==='prm_item_selected_icon'){circle(c,X,Y,R,'#1f8e80');line(c,[[w*.25,Y],[w*.43,h*.7],[w*.76,h*.3]],C.white,w*.08);
 }else if(name==='prm_premium_icon'){
  const pts=Array.from({length:10},(_,i)=>{const t=-Math.PI/2+i*Math.PI/5,r=i%2?R*.48:R;return [X+Math.cos(t)*r,Y+Math.sin(t)*r]});c.fillStyle=C.copper;c.beginPath();pts.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill();
 }else if(name==='prm_shop_icon'){round(c,w*.15,h*.27,w*.7,h*.62,3,C.silver);line(c,[[w*.32,h*.35],[w*.32,h*.15],[w*.68,h*.15],[w*.68,h*.35]],C.teal,2);
 }else if(name==='sotgReplay'||name==='sotgRewind'){
  round(c,2,2,w-4,h-4,Math.min(w,h)*.18,C.ink);c.strokeStyle=C.teal;c.lineWidth=Math.min(w,h)*.065;c.beginPath();c.arc(X,Y,R*.65,-1.1,4.4);c.stroke();line(c,[[X-R*.25,Y-R*.8],[X-R*.65,Y-R*.65],[X-R*.55,Y-R*.24]],C.white,Math.min(w,h)*.06);
 }else if(name==='timer'){
  circle(c,X,Y,R,C.ink);c.strokeStyle=C.silver;c.lineWidth=2;c.beginPath();c.arc(X,Y,R*.85,0,Math.PI*2);c.stroke();line(c,[[X,Y-R*.6],[X,Y],[X+R*.5,Y]],C.white,2);
 }else if(name==='visibilityOn'||name==='visibilityOff'){
  c.strokeStyle=C.white;c.lineWidth=3;c.beginPath();c.ellipse(X,Y,w*.36,h*.23,0,0,Math.PI*2);c.stroke();circle(c,X,Y,w*.1,C.teal);if(name==='visibilityOff')line(c,[[w*.2,h*.2],[w*.8,h*.8]],C.copper,5);
 }else if(name==='tutorial_arrow'){
  line(c,[[X,h*.88],[X,h*.16]],C.teal,w*.14);line(c,[[w*.2,h*.4],[X,h*.12],[w*.8,h*.4]],C.white,w*.11);
 }else if(name==='tutorial_side'||name==='sui_close_btn_side'||name==='sui_close_btn_middle'||name==='timer_mask'||name==='timer_bar'){
  round(c,0,0,w,h,Math.min(w,h)*.3,name==='timer_bar'?C.teal:'#17333d');
 }else throw Error('Unassigned original sprite '+name);
 return a.toBuffer('image/png');
}
async function main(){
 const kit=sharp(path.join(dir,'controls-generated.png'));
 // Crop coordinates describe only this newly generated image.
 const crops={btn_english:[35,125,315,315],power_meter:[388,235,380,100],cs_basic:[790,268,470,43],red_circle:[1295,190,215,215],btn_angle:[115,545,155,410],hand:[432,590,282,350],loading:[790,590,340,350],sotgPlay:[1180,595,335,340]};
 const pieces=[];
 for(const [name,b] of Object.entries(layout)){
  let png;
  if(crops[name]){const [left,top,width,height]=crops[name];png=await kit.clone().extract({left,top,width,height}).resize(b.w,b.h,{fit:'fill'}).png().toBuffer();}
  else if(name==='tutorial_finger'){const [left,top,width,height]=crops.hand;png=await kit.clone().extract({left,top,width,height}).resize(b.w,b.h,{fit:'contain',background:'#0000'}).png().toBuffer();}
  else png=await sharp(native(name,b.w,b.h)).resize(b.w,b.h).png().toBuffer();
  fs.writeFileSync(path.join(dir,name+'.png'),png);pieces.push({input:png,left:b.x,top:b.y});
 }
 const atlas=await sharp({create:{width:1343,height:625,channels:4,background:'#0000'}}).composite(pieces).webp({lossless:true}).toBuffer();
 fs.writeFileSync(path.join(dir,'ui.webp'),atlas);await sharp(atlas).png().toFile(path.join(dir,'atlas-preview.png'));
 // New geometry mask is drawn from technical dimensions, not copied alpha.
 const {data:src,info}=await sharp(path.join(dir,'table-generated.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const w=433,h=773,out=Buffer.alloc(w*h*4);
 const map=(v,points)=>{for(let i=1;i<points.length;i++)if(v<=points[i][0]){const [a,b]=points[i-1],[d,e]=points[i];return b+(v-a)*(e-b)/(d-a);}return points.at(-1)[1];};
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4;if(x<16||y<16||(x<80&&y<80&&Math.hypot(x-80,y-80)>64))continue;
  const sx=map(x,[[0,0],[16,22],[60,83],[83,120],[91,125],[433,420]])/433*info.width;
  const sy=map(y,[[0,0],[16,23],[84,120],[91,127],[773,734]])/773*info.height;
  const k=(Math.min(info.height-1,Math.round(sy))*info.width+Math.min(info.width-1,Math.round(sx)))*4;
  for(let c=0;c<3;c++)out[i+c]=src[k+c];out[i+3]=255;
  if(Math.hypot(x-83,y-84)<43||Math.hypot(x-60,y-773)<35){out[i]=3;out[i+1]=7;out[i+2]=10;}
 }
 const quarter=await sharp(out,{raw:{width:w,height:h,channels:4}}).webp({lossless:true}).toBuffer();fs.writeFileSync(path.join(dir,'table.webp'),quarter);
 const q=sharp(quarter),imgs=await Promise.all([q.clone().png().toBuffer(),q.clone().flop().png().toBuffer(),q.clone().flip().png().toBuffer(),q.clone().flip().flop().png().toBuffer()]);
 const full=await sharp({create:{width:w*2,height:h*2,channels:4,background:'#0b1820'}}).composite(imgs.map((input,i)=>({input,left:i%2*w,top:Math.floor(i/2)*h}))).png().toBuffer();await sharp(full).rotate(90).resize(1400).png().toFile(path.join(dir,'table-preview.png'));
 const cue=fs.readFileSync(path.join(dir,'cs_basic.png'));const moonMeta=await sharp(path.join(root,'game/images/cues/moon.webp')).metadata();await sharp(cue).resize(moonMeta.width,moonMeta.height).webp({lossless:true}).toFile(path.join(dir,'cue-moon.webp'));
 const bg=createCanvas(1024,1024),bc=bg.getContext('2d'),g=bc.createRadialGradient(512,460,10,512,512,800);g.addColorStop(0,'#263f48');g.addColorStop(1,'#080f18');bc.fillStyle=g;bc.fillRect(0,0,1024,1024);
 const bgMeta=await sharp(path.join(root,'game/games/pool/images/imported/themes/th_basic_background.webp')).metadata();await sharp(bg.toBuffer('image/png')).resize(bgMeta.width,bgMeta.height).webp({lossless:true}).toFile(path.join(dir,'background.webp'));
 for(const [file,outFile] of [['game/games/pool/images/imported/themes/th_basic_preview.webp','basic-preview.webp'],['game/images/themes/pool-emerald-preview.webp','emerald-preview.webp']]){const m=await sharp(path.join(root,file)).metadata();await sharp(quarter).resize(m.width,m.height).webp({lossless:true}).toFile(path.join(dir,outFile));}
 const hm=await sharp(path.join(root,'game/games/pool/images/imported/themes/th_basic_head_line.webp')).metadata();
 const hc=createCanvas(hm.width*4,hm.height*4),hctx=hc.getContext('2d');hctx.scale(4,4);for(let j=1;j<=3;j++)circle(hctx,hm.width*j/4,hm.height/2,Math.max(1,Math.min(hm.width,hm.height)*.14),C.copper);await sharp(hc.toBuffer('image/png')).resize(hm.width,hm.height).webp({lossless:true}).toFile(path.join(dir,'head-line.webp'));
 const report={sprites:Object.keys(layout).length,atlas:{width:1343,height:625},quarter:{width:w,height:h},svgUsed:false,oldArtworkRead:false,uiSha256:hash(atlas),tableSha256:hash(quarter)};fs.writeFileSync(path.join(dir,'build-report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
main().catch(e=>{console.error(e.stack);process.exit(1)});
