// Pack original flat sphere textures into their native UV regions; keep other sprites intact.
const sharp=require('sharp'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..');
(async()=>{
 const source=await sharp(path.join(__dirname,'original-assets/pyramid-ball-textures.png')).resize(2048,1024,{fit:'fill'}).png().toBuffer();
 const positions={0:[854,219],1:[984,219],2:[847,357],3:[977,357],4:[1107,357],5:[635,448],6:[765,448],7:[895,448],8:[1025,448],9:[1155,448],10:[1114,219],11:[717,291],12:[847,291],13:[977,291],14:[1107,291],15:[717,357]};
 const tiles=[];
 for(let id=0;id<16;id++)tiles.push({input:await sharp(source).extract({left:(id%4)*512+2,top:Math.floor(id/4)*256+2,width:508,height:252}).resize(128,64,{fit:'fill'}).png().toBuffer(),left:positions[id][0],top:positions[id][1]});
 const target=path.join(root,'game/games/pool/images/ui/pyramid-ui.webp');
 await sharp(path.join(root,'game/games/pool/images/ui/ui.webp')).composite(tiles).webp({lossless:true}).toFile(target);
 console.log('Original Pyramid sphere textures packed: yellow cue + white 1–15');
})().catch(error=>{console.error(error);process.exitCode=1;});
