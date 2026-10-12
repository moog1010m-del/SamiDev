const fs=require('fs'),path=require('path'),sharp=require('sharp');
const ROOT=path.resolve(__dirname,'..'), G=path.join(ROOT,'game'), TMP=path.join(ROOT,'design/original-assets');
const gen=JSON.parse(fs.readFileSync(path.join(TMP,'generation.json')));
for(const item of Object.values(gen))item.path=path.join(TMP,item.path);
const frames=n=>JSON.parse(fs.readFileSync(path.join(TMP,n+'-frames.json')));
const artDir=path.join(ROOT,'design/original-assets');fs.mkdirSync(artDir,{recursive:true});
const palette={red:'#cb6248',blue:'#3c87b2',green:'#328371',yellow:'#d7a134',dark:'#153945',cream:'#fff0cf',gold:'#cda66c'};
const records=[];
const defs='<defs><linearGradient id="gold" x2=".5" y2="1"><stop stop-color="#ffe2a7"/><stop offset="1" stop-color="#ab7344"/></linearGradient><radialGradient id="disc" cx=".36" cy=".3"><stop stop-color="#fffaf0"/><stop offset="1" stop-color="#d4b782"/></radialGradient><radialGradient id="glow"><stop stop-color="#fff8d8" stop-opacity=".65"/><stop offset="1" stop-color="#fff8d8" stop-opacity="0"/></radialGradient></defs>';
function svg(w,h,body,vw=100,vh=100){return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${vw} ${vh}" preserveAspectRatio="none">${defs}${body}</svg>`)}
const C=(x,y,r,fill,stroke='',sw=3)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${stroke?`stroke="${stroke}" stroke-width="${sw}"`:''}/>`;
const P=(d,fill='none',stroke='#fff',sw=7)=>`<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/>`;
const R=(x,y,w,h,fill,rx=6,stroke='',sw=3)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" ${stroke?`stroke="${stroke}" stroke-width="${sw}"`:''}/>`;
function diamond(fill=palette.gold){return P('M50 7 91 50 50 93 9 50Z',fill,'none',0)}
function star(fill='url(#gold)'){return P('M50 6 61 35 93 37 68 58 76 90 50 72 24 90 32 58 7 37 39 35Z',fill,'none',0)}
const digitPaths={0:'M30 12H70Q82 12 82 26V74Q82 88 70 88H30Q18 88 18 74V26Q18 12 30 12Z',1:'M32 28 52 12V88M32 88H75',2:'M18 28Q18 12 40 12H62Q82 12 82 32Q82 43 64 53L19 82V88H84',3:'M20 14H62Q82 14 82 32Q82 50 54 50Q82 50 82 70Q82 88 61 88H18',4:'M68 88V12L16 64H87',5:'M80 12H23V48H61Q83 48 83 69Q83 88 60 88H20',6:'M75 12H46Q19 12 19 47V68Q19 88 49 88Q81 88 81 66Q81 48 51 48H20',7:'M15 12H85L40 88',8:'M50 50Q20 50 20 30Q20 12 50 12Q80 12 80 30Q80 50 50 50Q17 50 17 70Q17 88 50 88Q83 88 83 70Q83 50 50 50',9:'M24 88H55Q82 88 82 55V32Q82 12 51 12Q20 12 20 34Q20 53 51 53H81'};
function number(n,color='#fff'){const s=String(n),width=100/s.length;return s.split('').map((d,i)=>`<g transform="translate(${width*i} 0) scale(${1/s.length} 1)">${d==='+'?P('M50 23V77M23 50H77','none',color,13):P(digitPaths[d]||digitPaths[0],'none',color,12)}</g>`).join('')}
function symbol(name,color='#fff'){
 if(/^\+?\d+$/.test(name))return number(name,color);
 if(name==='close'||name==='x')return P('M25 25 75 75M75 25 25 75','none',color,10);
 if(name==='plus')return P('M50 22V78M22 50H78','none',color,11);
 if(name==='arrow')return P('M50 90V14M20 44 50 14 80 44','none',color,12);
 if(name==='arrow_side')return P('M10 50H90M68 28 90 50 68 72M32 28 10 50 32 72','none',color,8);
 if(name==='reverse')return P('M17 37H82L65 18M83 63H18L35 82','none',color,10);
 if(name==='skip')return C(50,50,36,'none',color,11)+P('M24 24 76 76','none',color,10);
 if(name==='shield')return P('M17 18 50 7 83 18V52Q83 72 50 91Q17 72 17 52Z','none',color,9);
 if(name==='eye')return P('M7 50Q50 4 93 50Q50 96 7 50Z','none',color,7)+C(50,50,16,color);
 if(name==='ghost')return P('M17 91V37Q17 8 50 8Q83 8 83 37V91L67 81 50 92 33 81Z',color,'none',0)+C(37,43,5,palette.dark)+C(63,43,5,palette.dark)+C(50,63,5,palette.dark);
 if(name==='skull')return P('M23 66Q8 61 10 36Q10 9 50 9Q90 9 90 36Q92 61 77 66V87H23Z',color,'none',0)+C(32,42,10,palette.dark)+C(68,42,10,palette.dark)+P('M40 87V73M59 87V73','none',palette.dark,5);
 if(name==='clock')return C(50,50,39,'none',color,7)+P('M50 24V51L69 62','none',color,7);
 if(name==='check')return P('M18 50 40 72 83 26','none',color,11);
 if(name==='search')return C(42,42,25,'none',color,8)+P('M61 61 87 87','none',color,9);
 if(name==='heart')return P('M50 85 17 54Q-2 25 20 15Q37 7 50 27Q64 7 81 15Q104 25 83 54Z',color,'none',0);
 if(name==='help')return P('M27 28Q28 10 52 10Q78 10 78 32Q78 44 53 54V65','none',color,10)+C(53,85,6,color);
 if(name==='person')return C(50,31,19,color)+P('M14 90Q12 58 50 58Q88 58 86 90Z',color,'none',0);
 if(name==='calendar')return R(12,20,76,68,'none',8,color,6)+P('M30 10V30M70 10V30M12 39H88','none',color,6)+C(33,58,4,color)+C(52,58,4,color)+C(71,58,4,color)+C(33,74,4,color)+C(52,74,4,color);
 if(name==='flame')return P('M55 6Q78 34 70 47Q82 40 83 30Q103 73 68 91Q39 108 16 79Q2 56 31 27Q27 47 37 47Q50 39 55 6Z','url(#gold)','none',0)+P('M49 54Q74 80 52 89Q32 89 38 72Z',palette.cream,'none',0);
 if(name==='palm')return P('M50 25V60M50 26Q30 3 12 25M50 25Q71 3 89 25M50 28Q28 16 12 42M50 28Q71 16 88 42M50 26Q48 8 62 6M17 69Q45 84 83 94M84 67Q63 84 18 94','none',color,6)+P('M12 74 22 64M78 64 89 74','none',color,5);
 if(name==='friend')return `<g transform="translate(1 5) scale(.65)">${symbol('person',color)}</g><g transform="translate(47 33) scale(.5)">${symbol('plus',color)}</g>`;
 if(name==='report')return P('M20 92V12M20 14Q38 3 54 18Q73 30 89 16V60Q72 74 54 60Q38 46 20 56','none',color,7);
 if(name==='thumb_up')return P('M29 47 50 32 56 8Q70 5 70 22L66 42H85Q95 42 91 57L82 84H32Z',color,'none',0)+R(7,47,18,40,color,4);
 if(name==='thumb_down')return `<g transform="rotate(180 50 50)">${symbol('thumb_up',color)}</g>`;
 if(name==='edit')return P('M15 85 20 62 68 14Q76 6 86 16Q95 25 85 34L38 81Z','none',color,6)+P('M61 22 78 39M20 62 38 81','none',color,5);
 if(name==='camera')return R(8,28,84,58,'none',8,color,6)+P('M26 28 35 15H64L74 28','none',color,6)+C(50,57,18,'none',color,6);
 if(name==='settings')return C(50,50,26,'none',color,7)+C(50,50,9,'none',color,6)+Array.from({length:8},(_,i)=>`<g transform="rotate(${i*45} 50 50)">${P('M50 8V23','none',color,10)}</g>`).join('');
 if(name==='chevron')return P('M37 15 68 50 37 85','none',color,9);
 if(name==='robot')return R(15,25,70,60,palette.dark,15,palette.gold,5)+C(34,52,8,palette.cream)+C(66,52,8,palette.cream)+P('M37 70H63M50 10V25','none',palette.gold,5)+C(50,8,5,palette.gold);
 if(name==='finger')return P('M45 90 15 59Q10 48 20 44Q28 43 36 57V17Q36 5 47 5Q58 5 58 17V47Q68 33 76 47Q92 42 91 62L82 90Z',palette.cream,palette.dark,4);
 if(name==='gift')return R(16,37,68,52,palette.cream,5,palette.gold,4)+R(10,27,80,18,palette.dark,4,palette.gold,4)+P('M50 30V89M50 27Q10 22 24 9Q40 0 50 27Q60 0 76 9Q90 22 50 27','none',palette.gold,7);
 if(name==='crown')return P('M12 25 31 45 50 12 70 45 89 25 78 81H24Z','url(#gold)',palette.cream,3);
 if(name==='trophy')return P('M28 12H72V43Q72 65 50 65Q28 65 28 43Z','url(#gold)',palette.cream,3)+P('M28 20H11V32Q11 52 31 52M72 20H89V32Q89 52 69 52M50 65V86M28 90H72','none',palette.gold,8);
 if(name==='coin')return C(50,50,43,'url(#gold)',palette.cream,3)+`<g transform="translate(20 20) scale(.6)">${diamond(palette.dark)}</g>`;
 if(name==='spinner')return P('M77 19A40 40 0 1 1 24 18','none',color,10)+C(25,18,6,color);
 return star(color);
}
async function raster(w,h,body,vw=100,vh=100){return sharp(svg(w,h,body,vw,vh)).png().toBuffer()}
async function save(rel,buffer,source){const p=path.join(G,rel);fs.mkdirSync(path.dirname(p),{recursive:true});await sharp(buffer).toFormat(p.endsWith('.webp')?'webp':'png',{lossless:true}).toFile(p);records.push({path:'game/'+rel,source});}
async function alphaCrop(input,region){let s=sharp(input);if(region)s=s.extract(region);const {data,info}=await s.ensureAlpha().raw().toBuffer({resolveWithObject:true});let x0=info.width,y0=info.height,x1=-1,y1=-1;for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++)if(data[(y*info.width+x)*4+3]>180){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y)}if(x1<0)throw Error('empty generated crop');return sharp(data,{raw:info}).extract({left:x0,top:y0,width:x1-x0+1,height:y1-y0+1}).png().toBuffer()}
async function fit(input,w,h,padding=0){return sharp(input).resize(Math.max(1,w-2*padding),Math.max(1,h-2*padding),{fit:'fill'}).extend({top:padding,bottom:padding,left:padding,right:padding,background:'#00000000'}).png().toBuffer()}
async function composite(w,h,items){return sharp({create:{width:w,height:h,channels:4,background:'#00000000'}}).composite(items).png().toBuffer()}
const discCache={};
async function disc(w,h,kind){
 if(!discCache[kind]){const meta=await sharp(gen.carrom_discs.path).metadata();const cell=Math.floor(meta.width/4),index={white:0,black:1,red:2,striker:3}[kind];discCache[kind]=await alphaCrop(gen.carrom_discs.path,{left:index*cell,top:0,width:cell,height:meta.height});}
 return fit(discCache[kind],w,h,1);
}
async function board(variant){const source=await alphaCrop(gen[variant].path);const texture=await fit(source,1372,1372);let b='';const ink=variant==='board_cat'?'#3d556b':'#1c6666';
 // Render exact physical pockets in the existing 1428 px sprite coordinate system.
 const S=1080*1.1235/1428, at=x=>(x+1080*(1.1235-1)/2)/S;
 const pockets=[[102.12,99.264],[979.308,99.264],[102.12,986.448],[979.308,986.448]];
 for(const [x,y]of pockets)b+=C(at(x),at(y),58,'#071a20',palette.gold,5)+C(at(x),at(y),48,'#061218');
 for(let rot=0;rot<360;rot+=90){b+=`<g transform="rotate(${rot} 714 714)">`+R(350,at(194.4)-23,728,46,'none',23,ink,4)+C(350,at(194.4),23,ink)+C(1078,at(194.4),23,ink)+P('M295 295 390 390','none',ink,4)+P('M295 295 323 299M295 295 299 323','none',ink,4)+'</g>';}
 b+=C(714,714,86,'none',ink,4)+C(714,714,69,'none',ink,2)+`<g transform="translate(675 675) scale(.78)">${diamond(ink)}</g>`;
 const out=await composite(1428,1428,[{input:texture,left:28,top:28},{input:await raster(1428,1428,b,1428,1428),left:0,top:0}]);
 fs.writeFileSync(path.join(artDir,variant+'-finished.png'),out);return out;
}
async function carrom(boardImage,cat){const f=frames('carrom'),buffers={};for(const [name,rect]of Object.entries(f)){const {w,h}=rect;let out;
 if(name==='board_0')out=boardImage;
 else if(name.startsWith('carrom_'))out=await disc(w,h,name.split('_')[1]);
 else if(name==='strike_01')out=await disc(w,h,'striker');
 else if(name==='strike_base_0')out=await sharp(path.join(artDir,'carrom-slider-oak.png')).trim().resize(w,h,{fit:'fill'}).png().toBuffer();
 else if(['theme_preview','final','examples'].includes(name)){out=await fit(boardImage,w,h,8);if(name==='final'||name==='examples'){const d=await disc(Math.round(w*.075),Math.round(w*.075),'black');out=await sharp(out).composite([{input:d,left:Math.round(w*.3),top:Math.round(h*.35)}]).png().toBuffer()}}
 else if(name==='positioning'){out=await raster(w,h,R(2,17,96,65,palette.dark,14,palette.gold,2)+`<g transform="translate(20 20) scale(.6)">${symbol('arrow_side',palette.cream)}</g>`);}
 else if(name==='shoot'){out=await raster(w,h,`<g transform="translate(35 1) scale(.45)">${symbol('arrow',palette.gold)}</g><g transform="translate(30 43) scale(.55)">${symbol('finger')}</g>`);const d=await disc(Math.round(w*.32),Math.round(w*.32),'striker');out=await sharp(out).composite([{input:d,left:Math.round(w*.34),top:Math.round(h*.34)}]).png().toBuffer();}
 else if(name==='carroms_preview'){out=await composite(w,h,await Promise.all(['white','black','red'].map(async(k,i)=>({input:await disc(68,68,k),left:i*40,top:40}))));}
 else if(name==='arrow_line'||name==='separator'||name==='timer_bar')out=await raster(w,h,R(0,0,100,100,'#fff',0));
 else if(name==='arrow_outline'||name==='arrow_outline_fill')out=await raster(w,h,P('M5 40H65V12L96 50 65 88V60H5Z',name==='arrow_outline_fill'?'#fff':'none','#fff',5));
 else if(name==='striker_highlight'||name==='strike_circle')out=await raster(w,h,C(50,50,46,'none','#fff',name==='strike_circle'?2:5));
 else if(name==='empty_dot')out=await raster(w,h,C(50,50,34,'none',palette.cream,5));
 else if(name==='timer_mask')out=await raster(w,h,R(1,9,98,82,'none',20,'#fff',7));
 else if(name.startsWith('score_back'))out=await raster(w,h,R(2,6,96,90,palette.dark,12,palette.gold,2));
 else if(name==='target_points')out=await raster(w,h,`<g transform="translate(8 5) scale(.85)">${symbol('trophy')}</g>`);
 else if(name==='points_details')out=await raster(w,h,`<g transform="translate(6 8) scale(.8)">${symbol('coin')}</g>`);
 else {const map={close:'close',help:'help',loading:'spinner',premium_icon_large:'crown',timer:'clock',tutorial_arrow:'arrow',tutorial_finger:'finger',tutorial_side:'arrow_side'};out=await raster(w,h,symbol(map[name]||'star',palette.cream));}
 buffers[name]=out;}
 const atlas=await composite(3116,2128,Object.entries(f).map(([n,r])=>({input:buffers[n],left:r.x,top:r.y})));
 await save(cat?'images/themes/cat-atlas.webp':'images/game.webp',atlas,'generated board and discs + newly drawn functional sprites');
 await save(cat?'images/themes/cat-preview.webp':'images/themes/classic-preview.webp',await fit(boardImage,670,670,10),'new board composite');
}
async function crazy8(){const sheet=gen.card_surfaces.path;const crops=[[205,15,332,472],[602,15,334,472],[1000,15,335,472],[205,514,332,474],[602,514,334,474],[1000,514,335,474]];
 const surfaces=[];for(const [x,y,w,h]of crops)surfaces.push(await alphaCrop(sheet,{left:x,top:y,width:w,height:h}));
 const map={card_red:0,card_blue:1,card_green:2,card_yellow:3,card_dark_purple:4};let items=[];
 for(const [name,r]of Object.entries(frames('crazy8'))){let out;const {w,h}=r;
 if(name in map)out=await fit(surfaces[map[name]],w,h);
 else if(/^card_\d+$/.test(name))out=await raster(w,h,number(name.slice(5)));
 else if(/^(ellipse|notch)_/.test(name)){const wild=name.endsWith('wild');out=await raster(w,h,wild?`<clipPath id="d">${diamond('#fff')}</clipPath><g clip-path="url(#d)">${R(0,0,50,50,palette.red,0)+R(50,0,50,50,palette.yellow,0)+R(0,50,50,50,palette.blue,0)+R(50,50,50,50,palette.green,0)}</g>`:P('M50 4Q55 4 60 11L92 44Q99 50 92 57L59 89Q50 99 42 89L9 57Q2 50 9 43L42 11Q47 4 50 4Z','#fff','none',0));}
 else if(name.endsWith('_btn')){const color=palette[name.split('_')[0]];out=await raster(w,h,C(50,50,46,color,palette.cream,3)+C(50,50,36,'none',palette.gold,2));}
 else if(name.startsWith('draw2_')){const color=palette[name.slice(6)];out=await raster(w,h,R(14,27,48,65,color,6,palette.cream,4)+R(39,6,48,65,color,6,palette.cream,4));}
 else if(name==='draw4')out=await raster(w,h,R(5,25,40,55,palette.red,5,palette.cream,3)+R(23,13,40,55,palette.yellow,5,palette.cream,3)+R(40,25,40,55,palette.blue,5,palette.cream,3)+R(57,13,40,55,palette.green,5,palette.cream,3));
 else if(name==='blank')out=await raster(w,h,R(1,1,98,98,'#fff',7));
 else if(name==='card_mat_3')out=await raster(w,h,R(1,1,98,98,palette.dark,8,palette.gold,1.5));
 else if(name==='draw_card')out=await raster(w,h,R(1,4,98,92,palette.dark,15,palette.gold,2)+R(4,13,92,74,'none',11,palette.cream,1));
 else if(name==='badge')out=await raster(w,h,P('M28 48 18 95 49 80 81 95 72 48',palette.red,'none',0)+C(50,36,31,'url(#gold)',palette.cream,2)+`<g transform="translate(28 14) scale(.44)">${diamond(palette.dark)}</g>`);
 else if(name==='timer_mask')out=await raster(w,h,R(1,7,98,86,'none',25,'#fff',7));
 else {const keys={arrow_tut:'arrow',arrow:'arrow',card_draw2:'+2',card_draw4:'+4',card_reverse:'reverse',card_skip:'skip',ghost:'ghost',loading:'spinner',major_shield:'shield',minor_shield:'shield',major_x:'eye',minor_x:'x',premium_icon_large:'crown',skull:'skull',timer:'clock',trophy:'trophy'};out=await raster(w,h,symbol(keys[name]||'star'));}
 items.push({input:out,left:r.x,top:r.y});}
 await save('games/crazy8/images/MainSheet.webp',await composite(1142,1071,items),'generated card surfaces + newly drawn numbers and rule symbols');
 await save('games/crazy8/images/CardBackSheet.webp',await fit(surfaces[5],164,228),'generated original card back');
}
async function reactions(){const items=[];for(let n=0;n<12;n++){const r=frames('reactions')['r'+n],col=n%4,row=Math.floor(n/4),left=[34,379,725,1069][col],top=[38,372,707][row];const crop=await alphaCrop(gen.reactions.path,{left,top,width:332,height:330});items.push({input:await fit(crop,r.w,r.h,3),left:r.x,top:r.y});}return composite(562,432,items)}
function parseAtlas(file){let current=null;const out=[];for(const line of fs.readFileSync(file,'utf8').split(/\r?\n/)){if(!line||/^(size|filter|format|repeat|pma):/.test(line)||/\.(webp|png)$/.test(line))continue;if(!line.includes(':')){current={name:line,rotate:false};out.push(current)}else if(current){if(line.startsWith('bounds:'))[current.x,current.y,current.w,current.h]=line.slice(7).split(',').map(Number);if(line.startsWith('rotate:'))current.rotate=line.includes('90');}}return out.filter(r=>r.w)}
async function spine(file){const txt=fs.readFileSync(file,'utf8');const [w,h]=txt.match(/size:\s*(\d+),(\d+)/).slice(1).map(Number);const imageName=txt.split(/\r?\n/)[0];const items=[];for(const r of parseAtlas(file)){let b,color=Object.entries(palette).find(([c])=>r.name.includes(c))?.[1]||palette.cream;
 if(r.name.includes('glow')||r.name.startsWith('pulse/'))b=C(50,50,48,'url(#glow)');
 else if(r.name.startsWith('line_'))b=R(0,25,100,50,'#fff',10);
 else if(r.name==='player_indicator_ring')b=C(50,50,43,'none',palette.gold,6);
 else if(r.name==='player_indicator')b=diamond(palette.gold);
 else if(r.name.startsWith('reverse'))b=symbol('reverse',color);
 else if(r.name.startsWith('skip'))b=symbol('skip',color);
 else if(r.name.startsWith('arrow'))b=symbol('arrow',color);
 else {const m=r.name.match(/_(\d|plus)(?:_|$)/);b=symbol(m?.[1]==='plus'?'plus':m?.[1]||'star',color);}
 let img=await raster(r.w,r.h,b);if(r.rotate)img=await sharp(img).rotate(90).png().toBuffer();items.push({input:img,left:r.x,top:r.y});}
 const rel=path.relative(G,path.join(path.dirname(file),imageName));await save(rel,await composite(w,h,items),'new vector-derived animation frames, original frame layout retained');
}
async function shared(){const reaction=await reactions();for(const base of ['', 'games/crazy8/']){
 await save(base+'scene-reactions/reactions.webp',reaction,'generated reaction sheet');
 const icons={'scene-reactions/gift_icon.webp':['gift',128,128],'scene-avatars/lobby_avatar_empty_seat.png':['person',108,108],'scene-avatars/lobby_avatar_join.png':['plus',108,108],'scene-avatars/scene_avatars_bot.webp':['robot',300,300],'scene-avatars/scene_avatars_owner_badge.webp':['crown',120,113],'scene-ui/IAPButton/iap_button_icon.png':['gift',100,100],'scene-ui/ShopWidget/shop_widget_clear.webp':['close',24,24],'scene-ui/ShopWidget/shop_widget_coin.webp':['coin',48,48],'scene-ui/ShopWidget/shop_widget_equipped.webp':['check',30,30],'scene-ui/ShopWidget/shop_widget_favorite.webp':['heart',41,37],'scene-ui/ShopWidget/shop_widget_not_favorite.webp':['heart',41,37],'scene-ui/ShopWidget/shop_widget_loading.webp':['spinner',141,141],'scene-ui/ShopWidget/shop_widget_pip.webp':['star',56,56],'scene-ui/ShopWidget/shop_widget_search.webp':['search',40,40]};
 for(const [rel,[name,w,h]]of Object.entries(icons)){let b=symbol(name,palette.cream);if(rel.includes('not_favorite'))b=`<g opacity=".4">${b}</g>`;if(rel.includes('lobby_avatar'))b=C(50,50,47,palette.dark,palette.gold,2)+`<g transform="translate(17 17) scale(.66)">${b}</g>`;await save(base+rel,await raster(w,h,b),'new source-authored vector icon');}
 await spine(path.join(G,base,'scene-avatars/player_indicator.atlas'));
 }
 await save('images/default-avatar.png',await raster(320,320,C(50,50,49,palette.dark,palette.gold,2)+`<g transform="translate(15 15) scale(.7)">${symbol('person',palette.cream)}</g>`),'new source-authored default avatar');
 let sheet='';for(let i=0;i<11;i++)sheet+=`<g transform="translate(${i*32} 0) scale(.32)">${symbol(['star','trophy','calendar','flame','palm','friend','report','thumb_up','thumb_down','close','person'][i],palette.cream)}</g>`;fs.writeFileSync(path.join(G,'player-profile-sheet.svg'),svg(352,32,sheet,352,32));records.push({path:'game/player-profile-sheet.svg',source:'new source-authored vector icons'});
 const profileBase='platform/assets/profile/';
 const profileIcons={star:'star',trophy:'trophy',reputation:'flame','saudi-emblem':'palm',calendar:'calendar',camera:'camera',chevron:'chevron',settings:'settings',edit:'edit'};
 for(const [filename,key]of Object.entries(profileIcons)){const rel=profileBase+filename+'.svg';fs.writeFileSync(path.join(G,rel),svg(64,64,symbol(key,palette.gold)));records.push({path:'game/'+rel,source:'new source-authored profile icon'});}
 let profileSheet='';for(let i=0;i<7;i++)profileSheet+=`<g transform="translate(${i*64} 0) scale(.64)">${symbol(['star','trophy','calendar','flame','palm','edit','camera'][i],palette.gold)}</g>`;fs.writeFileSync(path.join(G,profileBase+'profile-sheet.svg'),svg(448,64,profileSheet,448,64));records.push({path:'game/'+profileBase+'profile-sheet.svg',source:'new source-authored profile sheet'});
 for(const [name,key]of Object.entries({star:'star',trophy:'trophy','reputation-flame':'flame','palm-swords':'palm',prestige:'crown'}))await save(profileBase+'raster/'+name+'.webp',await raster(256,256,symbol(key,palette.gold)),'new source-authored profile icon');
 for(const file of fs.readdirSync(path.join(G,'games/crazy8/anim')))if(file.endsWith('.atlas'))await spine(path.join(G,'games/crazy8/anim',file));
}
async function buildAll(){
 // Generated source images are included here; rebuilding never calls a remote image service.
 fs.writeFileSync(path.join(artDir,'generation-prompts.json'),JSON.stringify(Object.fromEntries(Object.entries(gen).map(([k,v])=>[k,{prompt:v.prompt,mode:'built-in image generation',transparentRequested:v.transparent,source:k+'.png'}])),null,2)+'\n');
 await carrom(await board('board_classic'),false);await carrom(await board('board_cat'),true);await crazy8();await shared();
 const bg=await sharp(gen.table_background.path).webp({quality:90}).toBuffer();for(const rel of ['images/table-background.webp','games/crazy8/images/table-background.webp']){fs.writeFileSync(path.join(G,rel),bg);records.push({path:'game/'+rel,source:'generated textile background'});}
 fs.writeFileSync(path.join(TMP,'visual-records.json'),JSON.stringify(records,null,2)+'\n');console.log(JSON.stringify({visualFiles:records.length,generatedSources:Object.keys(gen).length}));
}
module.exports={ROOT,G,artDir,gen,frames,records,palette,svg,raster,save,alphaCrop,fit,composite,disc,C,P,R,symbol,number,diamond,star,buildAll};
if(require.main===module)buildAll().catch(e=>{console.error(e);process.exitCode=1});
