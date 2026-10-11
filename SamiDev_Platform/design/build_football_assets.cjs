// Assemble independent art into the game's existing texture coordinates.
const fs=require('fs'),path=require('path'),sharp=require('sharp');
const A=require('./build_assets.cjs');
const {G,ROOT,artDir,gen,frames,records,palette,svg,raster,save,alphaCrop,fit,composite,C,P,R,symbol,diamond}=A;
const base='games/tablesoccer/';
const letters={G:'M82 25Q75 10 49 10Q17 10 17 49Q17 89 50 89Q80 89 82 66V53H56',O:'M50 10Q17 10 17 50Q17 90 50 90Q83 90 83 50Q83 10 50 10Z',A:'M12 89 46 11H55L89 89M27 60H75',L:'M22 10V88H83',P:'M20 90V10H56Q84 10 84 33Q84 56 56 56H20',S:'M80 16Q23 0 19 30Q16 48 50 50Q85 52 81 72Q78 100 19 85','!':'M50 10V61M50 84V87'};
function word(text,color=palette.cream){return [...text].map((c,i)=>`<g transform="translate(${i*100} 0)">${P(letters[c], 'none',color,10)}</g>`).join('')}
function pentagon(cx,cy,r,fill){let pts=[];for(let n=0;n<5;n++){let a=-Math.PI/2+n*Math.PI*2/5;pts.push([cx+Math.cos(a)*r,cy+Math.sin(a)*r].join(','))}return `<polygon points="${pts.join(' ')}" fill="${fill}"/>`}
function ball(){return C(50,50,46,palette.cream,palette.gold,2)+pentagon(50,50,19,palette.dark)+pentagon(50,10,12,palette.dark)+pentagon(89,39,12,palette.dark)+pentagon(75,86,12,palette.dark)+pentagon(24,86,12,palette.dark)+pentagon(11,39,12,palette.dark)+P('M50 31V19M68 44 79 40M61 65 69 77M39 65 30 77M32 44 20 40','none',palette.dark,2)}
async function buildField(){
 const texture=await sharp(gen.football_grass.path).resize(850,1394,{fit:'fill'}).png().toBuffer();
 const mask=await raster(850,1394,R(47,61,756,1272,'#fff',0)+R(295,0,260,1394,'#fff',0),850,1394);
 const grass=await sharp(texture).composite([{input:mask,blend:'dest-in'}]).png().toBuffer();
 let lines=R(47,61,756,1272,'none',0,palette.cream,5)+P('M47 697H803','none',palette.cream,5)+C(425,697,151,'none',palette.cream,5)+C(425,697,7,palette.cream);
 lines+=P('M247 61V166H603V61M247 1333V1228H603V1333','none',palette.cream,5)+P('M343 166Q425 235 507 166M343 1228Q425 1159 507 1228','none',palette.cream,5);
 let rail=R(28,40,19,1314,palette.dark,6,palette.gold,3)+R(803,40,19,1314,palette.dark,6,palette.gold,3);
 for(const y of [41,1335])rail+=R(46,y,249,20,palette.dark,3,palette.gold,3)+R(555,y,250,20,palette.dark,3,palette.gold,3);
 for(const x of [294,555]){rail+=R(x-2,0,4,61,palette.cream,0)+R(x-2,1333,4,61,palette.cream,0)}
 const field=await composite(850,1394,[{input:grass,left:0,top:0},{input:await raster(850,1394,lines+rail,850,1394),left:0,top:0}]);
 await save(base+'images/field-img-standard.png',await sharp(field).extract({left:0,top:0,width:425,height:1394}).png().toBuffer(),'generated turf + newly drawn exact pitch lines and rail geometry');
 fs.writeFileSync(path.join(artDir,'football-field-full.png'),field);return field;
}
async function build(){
 const field=await buildField();
 const bg=await sharp(gen.table_background.path).resize(540,960,{fit:'cover'}).png().toBuffer();await save(base+'images/bg-img-standard.png',bg,'generated textile arena background');
 let stadium=R(3,0,87,741,palette.dark,4,palette.gold,3);
 for(let y=16,row=0;y<741;y+=29,row++){stadium+=P(`M7 ${y+19}H83`,'none','#678987',2);for(let col=0;col<3;col++){const x=17+col*25;stadium+=R(x-8,y-4,17,19,row%3===0?palette.gold:col%2===0?'#377c81':'#557390',5)+C(x,y-5,4,'#f0d2a5');}}
 await save(base+'images/stadium-img-standard.png',await raster(101,741,stadium,101,741),'new vector stadium seating');
 const team=gen.football_team_tiles.path,m=await sharp(team).metadata(),half=Math.floor(m.width/2);const teams=[];
 for(let i=0;i<2;i++){const img=await sharp(team).extract({left:i*half,top:0,width:half,height:m.height}).resize(270,270).png().toBuffer();teams.push(img);await save(base+`images/default_${i?'away':'home'}.png`,img,'generated independent team emblem');}
 const thumbItems=[{input:await fit(field,160,264),left:175,top:15}];const thumbnail=await sharp(bg).resize(511,294,{fit:'cover'}).composite(thumbItems).png().toBuffer();await save(base+'images/thumbnail-standard.png',thumbnail,'new field and arena composite');
 const preview=await composite(350,250,[{input:await fit(teams[0],150,150),left:15,top:50},{input:await fit(teams[1],150,150),left:185,top:50}]);await save(base+'images/default_shop_preview.png',preview,'generated independent team emblem composite');
 let texture=R(0,0,256,128,palette.cream,0);for(let y=-16,row=0;y<160;y+=38,row++)for(let x=-20;x<290;x+=44)texture+=pentagon(x+(row%2)*22,y,12,palette.dark);await save(base+'images/ball-standard.png',await raster(256,128,texture,256,128),'new procedural sphere texture');
 let net=R(10,9,301,69,'#14353f',4,palette.gold,3);for(let x=20;x<309;x+=19)net+=P(`M${x} 12V74`,'none','#bdcdc3',1.5);for(let y=24;y<77;y+=14)net+=P(`M12 ${y}H310`,'none','#bdcdc3',1.5);net+=P('M11 75V100M310 75V100M11 75H310','none',palette.cream,9);
 const goal=await raster(321,112,net,321,112);await save(base+'images/goalpost-top-standard.png',goal,'new vector net and posts');await save(base+'images/goalpost-bottom-standard.png',goal,'new vector net and posts');
 const celebration=await raster(803,285,R(25,45,752,194,palette.dark,40,palette.gold,5)+`<g transform="translate(41 44) scale(1.95)">${ball()}</g><g transform="translate(270 73) scale(1.0 1.4)">${word('GOAL!')}</g>`,803,285);await save(base+'images/goal-scored-standard.png',celebration,'new ball and source-drawn goal lettering');
 for(const [i,w,h]of [[1,15,15],[2,15,20],[3,25,16],[4,18,11]])await save(base+`images/confetti-${i}-standard.png`,await raster(w,h,diamond([palette.gold,palette.cream,palette.blue,palette.red][i-1])),'new vector confetti');
 const items=[];
 for(const [name,r] of Object.entries(frames('football'))){let out;const {w,h}=r;
 if(name==='rules_1v1_active'){let entries=[{input:await fit(field,322,535),left:139,top:17}];for(let i=0;i<3;i++)entries.push({input:await fit(teams[0],59,59),left:194+i*76,top:340-(i%2)*75});entries.push({input:await raster(200,115,symbol('arrow',palette.cream)),left:228,top:184});out=await composite(w,h,entries);}
 else if(name==='formations')out=await fit(field,w,h,4);
 else if(name==='loading')out=await raster(w,h,symbol('spinner',palette.cream));
 else if(name==='black_circle')out=await raster(w,h,C(50,50,48,'#071d26'));
 else if(name==='arrow')out=await raster(w,h,P('M5 40H72V14L96 50 72 86V60H5Z','#fff','none',0));
 else if(name==='timer_bar')out=await raster(w,h,R(0,0,100,100,'#fff',0));
 else if(name==='timer_mask')out=await raster(w,h,R(2,5,96,90,'none',20,'#fff',4));
 else if(name==='timer')out=await raster(w,h,symbol('clock',palette.cream));
 else if(name==='star')out=await raster(w,h,symbol('star',palette.gold));
 else if(name==='dot')out=await raster(w,h,C(50,50,44,palette.cream));
 else if(name.startsWith('shadow'))out=await raster(w,h,C(50,50,42,name==='shadow_white'?'#ffffff66':'#00131d88'));
 else if(name.startsWith('player_light')){const col=name.endsWith('red')?palette.red:name.endsWith('neutral')?palette.cream:palette.blue;out=await raster(w,h,C(50,50,44,'none',col,6)+C(50,50,35,'none',col,2));}
 else if(['token_base','token_border','ts_circle'].includes(name))out=await raster(w,h,C(50,50,47,name==='token_base'?palette.dark:'none',palette.gold,4)+C(50,50,39,'none',palette.cream,2));
 else if(name==='ts_label')out=await raster(w,h,R(1,6,98,88,palette.dark,15,palette.gold,2));
 else if(name==='pass_balloon')out=await raster(w,h,R(2,2,246,76,palette.dark,15,palette.gold,2)+`<g transform="translate(23 9) scale(.5 .6)">${word('PASS')}</g>`,250,83);
 else if(name==='goal_balloon')out=await raster(w,h,R(1,2,98,86,palette.dark,14,palette.gold,2)+`<g transform="translate(14 10) scale(.72)">${ball()}</g>`);
 else {const map={bubble_fire:'flame',bubble_happy:'star',bubble_thumbsup:'thumb_up',bubble_clap:'friend',bubble_fireworks:'gift'};out=await raster(w,h,symbol(map[name]||'star',palette.gold));}
 items.push({input:out,left:r.x,top:r.y});}
 await save(base+'images/main.webp',await composite(995,871,items),'new functional sprites and new field composite');
 // Reuse the new shared artwork from the other games, never the old source assets.
 for(const dir of ['scene-avatars','scene-reactions','scene-ui']){const walk=d=>{for(const ent of fs.readdirSync(d,{withFileTypes:true})){const src=path.join(d,ent.name);if(ent.isDirectory())walk(src);else if(/\.(webp|png)$/.test(src)){const rel=path.relative(G,src);fs.copyFileSync(src,path.join(G,base,rel));records.push({path:'game/'+base+rel,source:'new shared game artwork'});}}};walk(path.join(G,dir));}
 fs.writeFileSync(path.join(artDir,'football-visual-records.json'),JSON.stringify(records,null,2)+'\n');console.log(JSON.stringify({footballVisualFiles:records.length,footballFrameCount:items.length}));
}
if(require.main===module)build().catch(e=>{console.error(e);process.exitCode=1});
module.exports={build};
