import {fileURLToPath} from 'node:url';import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import http from 'node:http';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const root=path.resolve(fileURLToPath(new URL('../game/',import.meta.url)));
const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+new URL(req.url,'http://local').pathname);if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}const types={'.html':'text/html; charset=utf-8','.js':'application/javascript','.json':'application/json','.png':'image/png','.webp':'image/webp','.css':'text/css','.m4a':'audio/mp4'};res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 for(const legacy of [true,false]){
  const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true});
  if(legacy)await page.route('**/browser-runtime.js*',async route=>{
   const response=await route.fetch();const text=(await response.text()).replace('stencil:isPool','stencil:false');
   await route.fulfill({response,body:text});
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/games/pool/index.html?play=1&clean=1');
  await page.waitForFunction(()=>window.__gameLogic?.sceneMgr&&window.__samidevGameState.localHost.started,{},{timeout:45000});
  const result=await page.evaluate(()=>{
   const canvas=document.getElementById('game'),gl=canvas.getContext('webgl');
   // Exercise the real default framebuffer used by the native pocket mask.
   // This page is closed afterwards: no game state or physics is changed.
   gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,canvas.width,canvas.height);
   gl.disable(gl.DEPTH_TEST);gl.disable(gl.BLEND);gl.disable(gl.CULL_FACE);gl.disable(gl.SCISSOR_TEST);gl.disable(gl.STENCIL_TEST);
   gl.colorMask(true,true,true,true);gl.clearColor(0,0,0,1);gl.clearStencil(0);gl.stencilMask(255);gl.clear(gl.COLOR_BUFFER_BIT|gl.STENCIL_BUFFER_BIT);
   gl.enable(gl.SCISSOR_TEST);gl.scissor(0,0,40,40);gl.clearStencil(1);gl.clear(gl.STENCIL_BUFFER_BIT);gl.disable(gl.SCISSOR_TEST);
   const make=(type,source)=>{const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));return shader;};
   const program=gl.createProgram();gl.attachShader(program,make(gl.VERTEX_SHADER,'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}'));gl.attachShader(program,make(gl.FRAGMENT_SHADER,'precision mediump float;void main(){gl_FragColor=vec4(1.);}'));gl.linkProgram(program);gl.useProgram(program);
   const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
   const location=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,2,gl.FLOAT,false,0,0);
   gl.enable(gl.STENCIL_TEST);gl.stencilFunc(gl.NOTEQUAL,0,255);gl.stencilOp(gl.KEEP,gl.KEEP,gl.KEEP);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
   const pixel=(x,y)=>{const a=new Uint8Array(4);gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,a);return Array.from(a);};
   return {stencil:gl.getContextAttributes().stencil,bits:gl.getParameter(gl.STENCIL_BITS),inside:pixel(20,20),outside:pixel(80,80),error:gl.getError()};
  });
  assert.deepEqual(result.inside,[255,255,255,255]);assert.equal(result.error,0);
  if(legacy){assert.equal(result.bits,0);assert.deepEqual(result.outside,[255,255,255,255],'missing stencil leaks a sinking sphere outside its mask');}
  else{assert.equal(result.stencil,true);assert(result.bits>=8);assert.deepEqual(result.outside,[0,0,0,255],'the pocket must occlude everything outside its mask');}
  console.log(JSON.stringify({legacy,...result}));await page.close();
 }
 console.log('POOL_POCKET_MASK_PASS: old framebuffer reproduces mask leakage; corrected renderer clips outside pocket; no physics modifications');
}catch(e){console.error(e);process.exitCode=1}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
