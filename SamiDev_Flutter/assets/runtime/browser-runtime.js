(() => {
  'use strict';

  const canvas = document.getElementById('game');
  const status = document.getElementById('status');
  const runtimeQuery = new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
  const runtimeDebug = runtimeQuery.get('debug') === '1';
  const currentGame = window.SamiDevGames.current();
  const isTableSoccer = currentGame.id === 'tablesoccer';
  const isPool = currentGame.id === 'pool';
  const isCrazy8 = currentGame.id === 'crazy8';
  const isCarrom = currentGame.id === 'carrom';
  const mobileDevice = Number(navigator.maxTouchPoints || 0) > 0 || !!window.matchMedia?.('(pointer: coarse)').matches;
  const HOST_GLOBAL = 'SamiDev';
  const HOST_PLAYER_ID_METHOD = 'getSamiDevID';
  const contextOptions = {alpha:true, antialias:!mobileDevice, preserveDrawingBuffer:false};
  const gl = canvas.getContext('webgl', contextOptions) || canvas.getContext('experimental-webgl', contextOptions);
  if (!gl) throw new Error('WebGL غير مدعوم في هذا المتصفح');

  const state = {
    surfaceCreated: null, surfaceChanged: null, drawFrame: null, touch: null, mouse: null,
    avatarsReady: null, menuClick: null, gameLogic: null, dict: {}, images: new Map(),
    frameRequested: true, nextHandle: 1,
    textures: new Map(), buffers: new Map(), framebuffers: new Map(), renderbuffers: new Map(),
    activePointers: new Map(), localHost: {hotseat:true, moves:[], alarms:new Map(), currentSeat:0, lastTurnKey:'', started:false},
    network: {online:false, waiting:false, roomId:null, roster:[], cosmetics:{}, seat:null, spectator:false, snapshotBusy:false, queuedSnapshot:null, finished:false, deferredMoves:[], authorityRevision:-1, authorityEpoch:null, pendingAuthority:null, authorityCheckTimer:null},
    surface: {w:0, h:0, menuY:0, initialized:false},
    performance: {mobile:mobileDevice, pixelRatio:1, frames:0, coalescedMoves:0},
  };
  window.__samidevGameState = state;
  if(isPool) window.SamiDevPoolCosmetics = {
    themeForSeat(seat) { return state.network.cosmetics?.[String(seat)]?.pool_theme === 'pool_emerald' ? 'pool_emerald' : 'pool_midnight'; },
    cueForSeat(seat) { return state.network.cosmetics?.[String(seat)]?.pool_cue === 'pool_cue_moon' ? 'pool_cue_moon' : 'pool_cue_classic'; }
  };

  function applyCosmetics(msg){
    if(!isPool || !msg?.cosmetics || typeof msg.cosmetics!=='object') return;
    state.network.cosmetics=msg.cosmetics;
    const logic=state.gameLogic;
    // Native syncItemDisplay/transitionItemDisplay own the table, cue and effect
    // lifecycle. Never replace a texture while a shot/transition is in progress.
    if(logic?.sceneMgr && !logic.paused && !logic.preshooting && !logic.animator?.isAnimatingWorld?.()) logic.syncItemDisplay();
  }

  const norm = (uri) => {
    if (typeof uri !== 'string') return uri;
    uri = uri.replace(/^~\//, '');
    uri = uri.replace(/^(?:carrom|tablesoccer|crazy8|pool)\//, '');
    return uri;
  };

  function syncText(uri) {
    const path = norm(uri);
    if (window.__textAssets && Object.prototype.hasOwnProperty.call(window.__textAssets, path)) return window.__textAssets[path];
    const xhr = new XMLHttpRequest();
    try { xhr.open('GET', path, false); xhr.send(null); } catch (e) { console.warn('loadFileAsString failed', path, e); return '{}'; }
    if (xhr.status >= 200 && xhr.status < 300 || xhr.status === 0) return xhr.responseText;
    console.warn('loadFileAsString HTTP', xhr.status, path);
    return '{}';
  }

  function intColorToCss(v) {
    v = Number(v) >>> 0;
    const a = ((v >>> 24) & 255) / 255;
    const r = (v >>> 16) & 255, g = (v >>> 8) & 255, b = v & 255;
    return `rgba(${r},${g},${b},${a})`;
  }

  function uploadCanvas(target, level, c) {
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(target, level, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    return {width:c.width, height:c.height};
  }

  function makeTextCanvas(text, opts={}) {
    if(isCrazy8 && typeof text==='string'){const you=/^You \((.*)\)$/.exec(text);if(you)text='أنت · '+you[1];}
    const size = Math.max(1, Number(opts.size) || 50);
    const fontName = (opts.font || 'Arial').replace(/^~/,'');
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d');
    ctx.font = `${opts.bold ? 'bold ' : ''}${size}px ${fontName}, Arial, sans-serif`;
    const lines = String(text ?? '').split('\n');
    let w = 1;
    for (const line of lines) w = Math.max(w, Math.ceil(ctx.measureText(line).width));
    c.width = Math.max(2, w + 8);
    c.height = Math.max(2, Math.ceil(lines.length * size * 1.3) + 8);
    ctx.font = `${opts.bold ? 'bold ' : ''}${size}px ${fontName}, Arial, sans-serif`;
    ctx.textBaseline = 'top';
    if (opts.background_color) { ctx.fillStyle = intColorToCss(opts.background_color); ctx.fillRect(0,0,c.width,c.height); }
    ctx.fillStyle = intColorToCss(opts.color ?? 0xffffffff);
    lines.forEach((line, i) => ctx.fillText(line, 4, 4 + i * size * 1.3));
    return c;
  }

  const idFor = (map, obj) => { const id = state.nextHandle++; map.set(id, obj); return id; };
  const objFor = (map, x) => typeof x === 'number' ? (map.get(x) || null) : x;
  function gen(map, create, n, out) { for (let i=0;i<n;i++) out[i] = idFor(map, create.call(gl)); }

  // Native main.js already has an avatar texture pipeline. Feed it the real profile
  // pictures instead of drawing a second HTML avatar on top of the game canvas.
  const profileAvatarTextureCache = new Map();
  let profileAvatarRefresh = 0;

  async function imageFromBlob(blob) {
    const url = URL.createObjectURL(blob);
    try {
      return await new Promise((resolve, reject) => {
        const img = new Image();
        img.decoding = 'async';
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('profile avatar image decode failed'));
        img.src = url;
      });
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  function uploadProfileAvatarTexture(img) {
    const tex = gl.createTexture();
    const id = idFor(state.textures, tex);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return {texture:id, x:0, y:0, width:img.naturalWidth||img.width, height:img.naturalHeight||img.height};
  }

  async function profileAvatarTexture(accountId) {
    const id = String(accountId || '').trim();
    const cacheKey = id || '__samidev_default_avatar__';
    if (profileAvatarTextureCache.has(cacheKey)) return profileAvatarTextureCache.get(cacheKey);
    const pending = (async () => {
      async function fetchImage(url) {
        const response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
        if (!response.ok || response.status === 204) return null;
        const blob = await response.blob();
        if (!blob.type.startsWith('image/') || blob.size === 0) return null;
        return uploadProfileAvatarTexture(await imageFromBlob(blob));
      }
      try {
        if (id) {
          const uploaded = await fetchImage(`/api/avatar/${encodeURIComponent(id)}`);
          if (uploaded) return uploaded;
        }
        return await fetchImage('/images/default-avatar.png');
      } catch (e) {
        if (runtimeDebug) console.warn('[SamiDev Avatar] load failed', id || 'default', e);
        return null;
      }
    })();
    profileAvatarTextureCache.set(cacheKey, pending);
    const result = await pending;
    if (!result && profileAvatarTextureCache.get(cacheKey) === pending) profileAvatarTextureCache.delete(cacheKey);
    return result;
  }

  async function refreshNativeAvatars() {
    if (!state.network.online || typeof state.avatarsReady !== 'function') return;
    const roster = Array.isArray(state.network.roster) ? state.network.roster.slice() : [];
    if (!roster.length) return;
    const refreshId = ++profileAvatarRefresh;
    const seats = Number(state.network.capacity) || Number(state.gameLogic?.seats) || roster.length;
    const bySeat = new Map(roster.filter(Boolean).map(p => [Number(p.seat), p]));
    const info = await Promise.all(Array.from({length:seats}, (_, seat) => profileAvatarTexture(bySeat.get(seat)?.accountId)));
    if (refreshId !== profileAvatarRefresh || typeof state.avatarsReady !== 'function') return;
    try { state.avatarsReady(info); state.frameRequested = true; }
    catch (e) { console.warn('[SamiDev Avatar] native avatar update failed', e); }
  }
  function del(map, deleter, n, arr) { for(let i=0;i<n;i++){ const id = arr[i]; const obj = map.get(id); if(obj) deleter.call(gl,obj); map.delete(id); } }

  const GL = {};
  const constants = [
    'ALWAYS','ARRAY_BUFFER','BACK','BLEND','CLAMP_TO_EDGE','COLOR_ATTACHMENT0','COLOR_BUFFER_BIT','COMPILE_STATUS','CULL_FACE','DECR_WRAP','DEPTH_ATTACHMENT','DEPTH_TEST','DYNAMIC_DRAW','ELEMENT_ARRAY_BUFFER','EQUAL','FLOAT','FRAGMENT_SHADER','FRAMEBUFFER','FRAMEBUFFER_COMPLETE','FRONT','INCR','INCR_WRAP','INVERT','KEEP','LINEAR','LINEAR_MIPMAP_LINEAR','LINEAR_MIPMAP_NEAREST','LINK_STATUS','MAX_TEXTURE_SIZE','NEAREST_MIPMAP_LINEAR','NEAREST_MIPMAP_NEAREST','NEVER','NONE','NOTEQUAL','ONE','ONE_MINUS_SRC_ALPHA','RENDERBUFFER','REPLACE','RGBA','SCISSOR_TEST','STATIC_DRAW','STENCIL_ATTACHMENT','STENCIL_BUFFER_BIT','STENCIL_TEST','TEXTURE0','TEXTURE_2D','TEXTURE_CUBE_MAP','TEXTURE_CUBE_MAP_POSITIVE_X','TEXTURE_MAG_FILTER','TEXTURE_MIN_FILTER','TEXTURE_WRAP_S','TEXTURE_WRAP_T','TRIANGLES','TRIANGLE_FAN','TRIANGLE_STRIP','UNSIGNED_BYTE','UNSIGNED_SHORT','VERTEX_SHADER','ZERO'
  ];
  constants.forEach(k => GL[k] = gl[k]);
  GL.__BOUND__ = 0;

  GL.genTextures=(n,out)=>gen(state.textures,gl.createTexture,n,out);
  GL.genBuffers=(n,out)=>gen(state.buffers,gl.createBuffer,n,out);
  GL.genFramebuffers=(n,out)=>gen(state.framebuffers,gl.createFramebuffer,n,out);
  GL.genRenderbuffers=(n,out)=>gen(state.renderbuffers,gl.createRenderbuffer,n,out);
  GL.deleteTextures=(n,a)=>del(state.textures,gl.deleteTexture,n,a);
  GL.deleteBuffers=(n,a)=>del(state.buffers,gl.deleteBuffer,n,a);
  GL.deleteFramebuffers=(n,a)=>del(state.framebuffers,gl.deleteFramebuffer,n,a);
  GL.deleteRenderbuffers=(n,a)=>del(state.renderbuffers,gl.deleteRenderbuffer,n,a);
  GL.bindTexture=(t,x)=>gl.bindTexture(t,objFor(state.textures,x));
  GL.bindBuffer=(t,x)=>gl.bindBuffer(t,objFor(state.buffers,x));
  GL.bindFramebuffer=(t,x)=>gl.bindFramebuffer(t,objFor(state.framebuffers,x));
  GL.bindRenderbuffer=(t,x)=>{ state.boundRenderbufferId=(typeof x==='number'?x:null); gl.bindRenderbuffer(t,objFor(state.renderbuffers,x)); };
  GL.framebufferTexture2D=(a,b,c,d,e)=>gl.framebufferTexture2D(a,b,c,objFor(state.textures,d),e);
  GL.framebufferRenderbuffer=(a,b,c,d)=>{
    const rb=objFor(state.renderbuffers,d);
    const meta=(typeof d==='number'?state.renderbufferMeta?.get(d):null);
    if(rb && meta?.packedDepthStencil && (b===gl.DEPTH_ATTACHMENT || b===gl.STENCIL_ATTACHMENT)){
      gl.framebufferRenderbuffer(a, gl.DEPTH_STENCIL_ATTACHMENT, c, rb);
      return;
    }
    gl.framebufferRenderbuffer(a,b,c,rb);
  };
  GL.bufferData=(target,size,data,usage)=>gl.bufferData(target,data ?? size,usage);
  GL.getIntegerv=(p,out)=>{ const v=gl.getParameter(p); out[0]=typeof v==='number'?v:0; };
  GL.getShaderiv=(s,p,out)=>{ out[0]=gl.getShaderParameter(s,p)?1:0; };
  GL.getProgramiv=(p,n,out)=>{ out[0]=gl.getProgramParameter(p,n)?1:0; };
  GL.getShaderInfoLog=(s)=>gl.getShaderInfoLog(s)||'';
  GL.getProgramInfoLog=(p)=>gl.getProgramInfoLog(p)||'';
  GL.texImage2D=(...a)=>gl.texImage2D(...a);
  GL.texImage2DFromFile=(target,level,uri,border)=>{
    const path=norm(uri), img=state.images.get(path);
    if (img) {
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);
      gl.texImage2D(target,level,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
      return {width:img.naturalWidth||img.width,height:img.naturalHeight||img.height};
    }
    console.warn('Missing preloaded texture',uri,'=>',path);
    const px=new Uint8Array([255,0,255,255, 0,0,0,255, 0,0,0,255, 255,0,255,255]);
    gl.texImage2D(target,level,gl.RGBA,2,2,0,gl.RGBA,gl.UNSIGNED_BYTE,px);
    return {width:2,height:2};
  };
  GL.texImage2DFromText=(target,level,text,border,opts)=>uploadCanvas(gl.TEXTURE_2D,level,makeTextCanvas(text,opts));
  GL.texImage2DFromTextRich=(rich,opts)=>{
    let text='';
    try {
      if (typeof rich === 'string') text=rich;
      else if (Array.isArray(rich)) text=rich.map(x=>x.text||x.value||'').join('');
      else text=rich?.text || rich?.value || String(rich ?? '');
    } catch { text=''; }
    return uploadCanvas(gl.TEXTURE_2D,0,makeTextCanvas(text,opts||{}));
  };
  GL.resetBoundTexture=()=>{};
  GL.flush=()=>gl.flush();

  // Methods whose signatures match WebGL directly.
  const packedDepthStencil = gl.getExtension('OES_packed_depth_stencil');
  state.renderbufferMeta = new Map();
  GL.renderbufferStorage=(target,format,w,h)=>{
    const packed = format===35056 || format===gl.DEPTH_STENCIL;
    if(Number.isInteger(state.boundRenderbufferId)) state.renderbufferMeta.set(state.boundRenderbufferId,{packedDepthStencil:packed,format});
    gl.renderbufferStorage(target, packed ? (packedDepthStencil?.DEPTH_STENCIL_OES || gl.DEPTH_STENCIL) : format, w,h);
  };
  ['activeTexture','attachShader','blendFunc','checkFramebufferStatus','clear','clearColor','clearStencil','colorMask','compileShader','createProgram','createShader','cullFace','disable','disableVertexAttribArray','drawArrays','drawElements','enable','enableVertexAttribArray','generateMipmap','getAttribLocation','getUniformLocation','lineWidth','linkProgram','scissor','shaderSource','stencilFunc','stencilMask','stencilOp','texParameteri','uniform1i','useProgram','vertexAttribPointer','viewport'].forEach(name=>{
    GL[name]=(...args)=>gl[name](...args);
  });
  ['uniform1f','uniform2f','uniform3f','uniform4f','uniform1i','uniform2i','uniform3i','uniform4i'].forEach(name=>{ GL[name]=(...args)=>gl[name](...args); });
  ['uniform1fv','uniform2fv','uniform3fv','uniform4fv','uniform1iv','uniform2iv','uniform3iv','uniform4iv'].forEach(name=>{
    GL[name]=(loc,countOrValue,value)=>gl[name](loc,value ?? countOrValue);
  });
  GL.uniformMatrix3fv=(loc,a,b,c)=>{ const value=c ?? b ?? a; const transpose=(c!==undefined?b:false); gl.uniformMatrix3fv(loc,!!transpose,value); };
  GL.uniformMatrix4fv=(loc,a,b,c)=>{ const value=c ?? b ?? a; const transpose=(c!==undefined?b:false); gl.uniformMatrix4fv(loc,!!transpose,value); };
  window.GL = GL;

  // Audio bridge for browser playback. Browsers may require the first user gesture before audio can start.
  const audios = new Map(); let audioId=1;
  const effectUri = uri => { const path=norm(uri); return path + (path.includes('?') ? '&' : '?') + 'v=audio37'; };

  window.AudioController = { musicVolume: 1 };
  window.pmath = {sin:Math.sin, cos:Math.cos, atan2:Math.atan2, acos:Math.acos, pow:Math.pow};


  window.audio = {
    load(uri){ const id=audioId++; const a=new Audio(effectUri(uri)); audios.set(id,a); return id; },
    unload(id){ const a=audios.get(id); if(a){a.pause();audios.delete(id);} },
    suspend(){ window.__SAMIDEV_AUDIO_SUSPENDED=true; for(const a of audios.values())a.pause(); window.__music?.pause(); },
    resume(){ window.__SAMIDEV_AUDIO_SUSPENDED=false; },
    play(id,volume=1){ if(window.__SAMIDEV_AUDIO_SUSPENDED||hostBridge.game_preferences?.mute)return; const a=audios.get(id); if(a){a.volume=Math.max(0,Math.min(1,volume));a.currentTime=0;a.play().catch(()=>{});} },
    playMusic(uri,volume=1){ if(window.__SAMIDEV_AUDIO_SUSPENDED||hostBridge.game_preferences?.mute)return; const a=new Audio(norm(uri)); a.loop=true;a.volume=volume;a.play().catch(()=>{}); window.__music=a; },
    stopMusic(){ window.__music?.pause(); }
  };

  function translate(args) {
    if (!Array.isArray(args)) args=[args];
    const key=String(args[0] ?? '');
    let s=state.dict[key] ?? key.replace(/^_/, '').replaceAll('_',' ');
    args.slice(1).forEach((v,i)=>{ s=s.replaceAll(`{${i}}`,String(v)); });
    return s;
  }

  function loadJsonStorage(key, fallback={}) {
    try { const v=localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  }
  function saveJsonStorage(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value ?? {})); } catch {}
  }

  const timers=new Map(); let timerId=1;
  const setHostTimer=(fn,ms,repeat=false)=>{
    const id=timerId++;
    // The native carrom renderer schedules its first-play tutorial on sync.
    // Postpone that presentation callback until the waiting scene is released.
    const tutorial=isCarrom&&!repeat&&String(fn).includes('openTutorial');
    const run=()=>{
      if(tutorial&&state.network.waiting){const timer=timers.get(id);if(timer)timer.real=setTimeout(run,100);return;}
      timers.delete(id);fn();
    };
    const real=repeat?setInterval(fn,ms):setTimeout(run,ms);timers.set(id,{real,repeat});return id;
  };
  const clearHostTimer=(id)=>{ const t=timers.get(id); if(!t)return; t.repeat?clearInterval(t.real):clearTimeout(t.real); timers.delete(id); };

  const hostBridge = {
    // Keep production consoles quiet. Append ?debug=1 when Trace/Debug logs are needed.
    globals:{}, is_server:false, is_develop:runtimeDebug, mobileUI:mobileDevice, version:30, dpi:96, language:'en', os:'web', isRTL:()=>false,
    ownerSeat:()=>0, saved_local_state:loadJsonStorage(`samidev.${currentGame.id}.saved_local_state`,{}), game_preferences:loadJsonStorage(`samidev.${currentGame.id}.game_preferences`,isPool?{"@SamiDev/sound":{enabled:true,volume:1,music:false}}:{}),
    log:(m,l)=>{ const level=Number(l); if(runtimeDebug) console.log('[game]',m); else if(Number.isFinite(level) && level>=4) console.error('[game]',m); else if(Number.isFinite(level) && level>=3) console.warn('[game]',m); }, hrtime:()=>performance.now()*1e6,
    translate, loadFileAsString:syncText,
    saveLocalState:(x)=>{ hostBridge.saved_local_state=x||{}; saveJsonStorage(`samidev.${currentGame.id}.saved_local_state`,hostBridge.saved_local_state); }, saveGamePreferences:(x)=>{hostBridge.game_preferences=x||{}; saveJsonStorage(`samidev.${currentGame.id}.game_preferences`,hostBridge.game_preferences);},
    setTimer:setHostTimer, clearTimer:clearHostTimer, requestRender:()=>{state.frameRequested=true;},
    addMenuButton:(id,label)=>{ (state.menuButtons||(state.menuButtons=[])).push({id,label}); }, requestKeyboard:()=>{}, showGameOver:()=>console.log('[web-host] Game over'), showItemPurchase:()=>{}, showProfile:(seat)=>{ try { const player=(window.SamiDevNetwork?.state?.roster||[]).find(p=>p&&Number(p.seat)===Number(seat)); if(window.SamiDevMobile?.postMessage&&player?.accountId){window.SamiDevMobile.postMessage(JSON.stringify({type:'open_player_profile',userId:player.accountId}));}else{window.SamiDevPlayerProfileUI?.openSeat?.(seat);} } catch (e) { console.warn('[SamiDev Profile] native profile open failed', e); } }, track:()=>{},
    getInventory:()=>[], [HOST_PLAYER_ID_METHOD]:(seat)=> { const r=state.network.roster?.find?.(x=>x&&x.seat===seat); return Number.isInteger(seat)&&seat>=0?(r?.name||(state.network.waiting?null:`Player ${seat+1}`)):null; },
    haptic:{isVibrationSupported:()=>typeof navigator!=='undefined'&&typeof navigator.vibrate==='function',vibrate:(ms=20)=>{try{navigator.vibrate?.(ms);}catch(_){}},vibratePattern:(p)=>{try{navigator.vibrate?.(p);}catch(_){}}},
    shop:{getCatalog:()=>Promise.resolve([])},
    net:{sendMessage:()=>{}, onMessage:()=>{}},
    setOnSurfaceCreatedListener:(f)=>state.surfaceCreated=f,
    setOnSurfaceChangedListener:(f)=>state.surfaceChanged=f,
    setOnDrawFrameListener:(f)=>state.drawFrame=f,
    setOnTouchListener:(f)=>state.touch=f,
    setOnMouseListener:(f)=>state.mouse=f,
    setOnAvatarsReadyListener:(f)=>{state.avatarsReady=f;queueMicrotask(()=>refreshNativeAvatars());},
    setOnMenuButtonClickedListener:(f)=>state.menuClick=f,
    fetchAudio:(uri,ok,fail)=>{ try{ const id=audioId++; const a=new Audio(effectUri(uri)); audios.set(id,a); ok?.(uri,{audio_id:id}); }catch(e){fail?.(uri,e);} },
    fetchTexture:(uri,ok,fail)=>{
      const path=norm(uri), img=state.images.get(path);
      if(!img){ fail?.(uri,'not preloaded'); return; }
      const tex=gl.createTexture(), id=idFor(state.textures,tex);
      gl.bindTexture(gl.TEXTURE_2D,tex); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      ok?.(uri,{texture_id:id,width:img.naturalWidth||img.width,height:img.naturalHeight||img.height});
    },
    streamMusic:(uri,cb)=>{ cb?.(uri,0); },
    alarm:{set:(ms,id)=>scheduleLogicAlarm(ms,id)},
    session:{changeTurn:(turn,msg)=>{ try{ state.gameLogic?.changeTurn?.(turn,msg); }catch(e){console.warn('changeTurn',e);} },gameOver:(...a)=>console.log('[web-host] gameOver',...a)},
    sendMove:(move)=>{
      if(state.network.waiting)return false;
      if(isPool && state.network.online && move?.__info!==undefined){
        // Native animation reports are presentation-only. Never send client results.
        setTimeout(()=>waitUntilWorldSettles(state.gameLogic,20000).then(()=>window.SamiDevNetwork?.requestResync?.()),100);
        return true;
      }
      return state.network.online?window.SamiDevNetwork?.sendMove?.(move):ackLocalMove(move);
    }, resetSynchronizationStream:()=>state.network.waiting?false:state.network.online?window.SamiDevNetwork?.requestResync?.():localResync(),
    setGameLogic:(logic)=>{ state.gameLogic=logic; window.__gameLogic=logic; window.SamiDevCardAudio?.bindLocal(logic); }
  };
  window[HOST_GLOBAL]=hostBridge;

  async function resignOnlineMatch(timeoutMs=4500) {
    const logic = state.gameLogic;
    const net = window.SamiDevNetwork;
    if (!state.network.online || !net || !logic) return {ok:false, code:'NOT_READY'};
    const seat = Number(logic.localSeat);
    if (!Number.isInteger(seat) || seat < 0) return {ok:false, code:'NO_LOCAL_SEAT'};
    if (logic.gameOver || logic.isResigned?.(seat)) return {ok:true, alreadyFinished:true, gameOver:!!logic.gameOver};

    // The native menu uses localMove({m:4}) for resignation. Keep that exact game
    // semantic so the authoritative headless main.js decides the finish order/winner.
    const acknowledged = new Promise(resolve => {
      let done = false;
      let offMove = () => {};
      let offError = () => {};
      const finish = value => {
        if (done) return;
        done = true;
        offMove(); offError(); clearTimeout(timer);
        resolve(value);
      };
      offMove = net.on('move', msg => {
        const kind = Number(isCrazy8 ? msg?.packet?.m?.q : (isTableSoccer || isPool) ? msg?.packet?.m?.a : msg?.packet?.m?.m);
        if (Number(msg?.seat) === seat && kind === (isPool ? 0 : isCrazy8 ? 1 : isTableSoccer ? 3 : 4)) {
          finish({ok:true, gameOver:!!msg?.authority?.gameOver, message:msg});
        }
      });
      offError = net.on('error', msg => {
        if (msg?.code === 'MOVE_REJECTED' || msg?.code === 'DESYNC') finish({ok:false, code:msg.code, error:msg});
      });
      const timer = setTimeout(() => finish({ok:false, code:'RESIGN_TIMEOUT'}), Math.max(1000, Number(timeoutMs)||4500));
    });

    // A shot animation can temporarily pause local moves. Give the native runtime a
    // short chance to resume; if it does not, use the same m:4 packet directly with
    // the current native sequence. The server still validates it with main.js.
    const until = performance.now() + 1800;
    while (logic.paused && performance.now() < until && !logic.gameOver) {
      await new Promise(resolve => setTimeout(resolve, 30));
    }

    let sent = false;
    try { sent = logic.localMove(isPool ? {a:0} : isCrazy8 ? {q:1} : isTableSoccer ? {a:3} : {m:4}, false) === true; }
    catch (e) { if (runtimeDebug) console.warn('[SamiDev UI] native resign localMove failed', e); }
    if (!sent && !logic.gameOver) {
      const sequence = Number(logic._sequence?.[seat]);
      if (Number.isInteger(sequence) && sequence >= 0) {
        sent = net.sendMove({i:`web-resign-${Date.now()}-${seat}`, m:isPool ? {a:0} : isCrazy8 ? {q:1} : isTableSoccer ? {a:3} : {m:4}, n:sequence}) === true;
      }
    }
    if (!sent) return {ok:!!logic.gameOver, code:logic.gameOver ? undefined : 'RESIGN_SEND_FAILED', gameOver:!!logic.gameOver};
    return acknowledged;
  }

  // Small public UI adapter. It reuses main.js's own menu handlers instead of
  // duplicating game behavior in the browser shell.
  window.SamiDevGameUI = {
    invokeMenu(id){
      if(typeof state.menuClick !== 'function') return false;
      try { state.menuClick(String(id)); state.frameRequested=true; return true; }
      catch(e){ console.warn('[SamiDev UI] menu action failed', id, e); return false; }
    },
    canHelp(){ return (state.menuButtons||[]).some(button=>button.id==='howto'); },
    openHelp(){ return this.canHelp() && this.invokeMenu('howto'); },
    toggleSound(){
      const preferences={...(hostBridge.game_preferences||{}),mute:!this.isMuted()};
      hostBridge.saveGamePreferences(preferences);
      if(preferences.mute){for(const a of audios.values())a.pause();window.__music?.pause();window.SamiDevCardAudio?.stop();}
      return true;
    },
    resignMatch(timeoutMs){ return resignOnlineMatch(timeoutMs); },
    isGameOver(){ return !!state.gameLogic?.gameOver; },
    isMuted(){ return !!hostBridge.game_preferences?.mute; },
    getPreferences(){ return {...(hostBridge.game_preferences || {})}; },
  };

  function resize() {
    const rect=canvas.getBoundingClientRect();
    // A transient collapsed layout can happen while CSS/viewport state is settling.
    // Returning false lets startup wait for a usable surface instead of hiding the loader
    // and leaving WebGL at main.js's white clear color forever. Runtime changes are also
    // observed by ResizeObserver below, so a later valid size cannot be missed.
    if(rect.width < 8 || rect.height < 8) return false;
    // Keep CSS/scene geometry unchanged while limiting phone fill-rate and buffer memory.
    const dpr=Math.min(devicePixelRatio||1, mobileDevice ? 1.5 : 2,
      mobileDevice ? Math.sqrt(1000000/(rect.width*rect.height)) : Infinity);
    state.performance.pixelRatio=dpr;
    const w=Math.max(1,Math.round(rect.width*dpr)), h=Math.max(1,Math.round(rect.height*dpr));
    const menuY=90*dpr;
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}

    // ResizeObserver is installed before main.js finishes loading. It may observe a perfectly
    // valid canvas before main.js has registered surfaceChanged. Do NOT mark that measurement
    // initialized: otherwise the real startup resize would be deduplicated and the game would
    // stay at WebGL's white clear color without ever receiving its first surfaceChanged().
    if(typeof state.surfaceChanged!=='function') return false;

    // Browsers can emit duplicate resize events with exactly the same physical surface.
    // main.js treats every surfaceChanged as a full client sync; while paused that can also
    // trigger a resync. Deduplicating here prevents timer/UI resets and console floods.
    if(state.surface.initialized && state.surface.w===w && state.surface.h===h && state.surface.menuY===menuY) return true;
    state.surface.w=w;
    state.surface.h=h;
    state.surface.menuY=menuY;
    state.surface.initialized=true;

    // Game.surfaceChange() ends by calling Game.sync(), which invokes CarromLogic.onSync()
    // and sets _syncCalledFlag=true. That flag is specifically used by the 500ms
    // animationCompleted() turn timer to suppress stale post-shot transitions after an
    // authoritative sync. A visual viewport resize is not an authoritative state sync, so
    // preserve a false flag across surfaceChanged; otherwise a resize can cancel the local
    // next-turn transition and make both clients display "opponent's turn".
    const logic=state.gameLogic;
    const syncFlagBefore=logic?._syncCalledFlag;
    state.surfaceChanged?.(w,h,0,menuY);
    if(state.network.online && logic && syncFlagBefore===false && logic._syncCalledFlag===true && !state.network.snapshotBusy){
      logic._syncCalledFlag=false;
      if(runtimeDebug) console.debug('[SamiDev Sync] visual resize preserved pending turn transition');
    }
    state.frameRequested=true;
    return true;
  }

  async function ensureInitialSurface(timeoutMs=5000) {
    const started=performance.now();
    while(!resize()){
      if(performance.now()-started>=timeoutMs) throw new Error('تعذر تهيئة سطح اللعبة: أبعاد Canvas غير صالحة');
      await new Promise(resolve=>requestAnimationFrame(resolve));
    }
  }

  function eventPoint(ev) {
    const r=canvas.getBoundingClientRect();
    return {id:ev.pointerId ?? 0, x:(ev.clientX-r.left)*(canvas.width/Math.max(1,r.width)), y:(ev.clientY-r.top)*(canvas.height/Math.max(1,r.height))};
  }

  // SamiDev touch input uses a bottom-left physical origin. main.js InputManager
  // flips Y back into scene coordinates. DOM pointer events use top-left, so touch
  // events must be converted here. MouseManager does not flip Y, therefore mouse
  // events intentionally keep using eventPoint() unchanged.
  function touchPoint(ev) {
    const p=eventPoint(ev);
    return {id:p.id, x:p.x, y:canvas.height-p.y};
  }

  function emitTouch(action, ev) {
    if(!state.touch) return;
    const p=touchPoint(ev);
    if(action===0 || action===2) state.activePointers.set(p.id,p);
    if(action===1 || action===3 || action===4) state.activePointers.set(p.id,p);
    // Pass an immutable snapshot to main.js; gesture processing may retain/mutate points.
    const pointers=Array.from(state.activePointers.values(),q=>({id:q.id,x:q.x,y:q.y}));
    try { state.touch({action,pointers}); } catch(e){ console.warn('[web-host] touch',e); }
    if(action===1 || action===3 || action===4) state.activePointers.delete(p.id);
    state.frameRequested=true;
  }

  function emitMouse(mask, ev) {
    if(!state.mouse) return;
    const p=eventPoint(ev);
    try { state.mouse({x:p.x,y:p.y,mask,button:ev.button??0,buttons:ev.buttons??0,alt:!!ev.altKey,control:!!ev.ctrlKey,shift:!!ev.shiftKey}); } catch(e){ console.warn('[web-host] mouse',e); }
  }

  const pendingPointerMoves = new Map();
  function deliverPointerMove(ev) {
    const pointerId=ev.pointerId ?? 0;
    const dragging=state.activePointers.has(pointerId) || Number(ev.buttons||0)>0;
    if(dragging) emitTouch(2,ev);
    if(ev.pointerType!=='touch') emitMouse('move',ev);
  }
  function flushPointerMoves() {
    const pending=Array.from(pendingPointerMoves.values());
    pendingPointerMoves.clear();
    for(const ev of pending) deliverPointerMove(ev);
  }
  function installInputBridge() {
    canvas.style.touchAction='none';
    canvas.style.userSelect='none';
    canvas.addEventListener('pointerdown',ev=>{ ev.preventDefault(); try{canvas.setPointerCapture(ev.pointerId);}catch{}; emitTouch(0,ev); if(ev.pointerType!=='touch') emitMouse('down',ev); unlockAudio(); },{passive:false});
    canvas.addEventListener('pointermove',ev=>{
      ev.preventDefault();
      // Mouse/pen hover is not a SamiDev touch MOVE. Only forward drag moves after DOWN.
      // Touch pointers do not have a meaningful hover state, so an active pointer is enough.
      const pointerId=ev.pointerId ?? 0;
      if(pendingPointerMoves.has(pointerId)) state.performance.coalescedMoves++;
      pendingPointerMoves.set(pointerId, {pointerId, pointerType:ev.pointerType, clientX:ev.clientX, clientY:ev.clientY,
        button:ev.button, buttons:ev.buttons, altKey:ev.altKey, ctrlKey:ev.ctrlKey, shiftKey:ev.shiftKey});
    },{passive:false});
    canvas.addEventListener('pointerup',ev=>{ ev.preventDefault(); flushPointerMoves(); emitTouch(1,ev); if(ev.pointerType!=='touch') emitMouse('up',ev); try{canvas.releasePointerCapture(ev.pointerId);}catch{}; },{passive:false});
    canvas.addEventListener('pointercancel',ev=>{ ev.preventDefault(); pendingPointerMoves.delete(ev.pointerId??0); emitTouch(3,ev); if(ev.pointerType!=='touch') emitMouse('leave',ev); },{passive:false});
    canvas.addEventListener('pointerenter',ev=>{if(ev.pointerType!=='touch') emitMouse('enter',ev);});
    canvas.addEventListener('pointerleave',ev=>{if(ev.pointerType!=='touch') emitMouse('leave',ev);});
    canvas.addEventListener('lostpointercapture',ev=>{
      const id=ev.pointerId??0;
      if(state.activePointers.has(id)){pendingPointerMoves.delete(id);emitTouch(3,ev);}
    });
    canvas.addEventListener('contextmenu',ev=>ev.preventDefault());
  }

  function unlockAudio(){
    // A no-op user gesture is enough for HTMLAudioElement playback permission in most browsers.
    if(window.__music && window.__music.paused) window.__music.play().catch(()=>{});
  }

  function scheduleLogicAlarm(ms,id){
    const logic=state.gameLogic; if(!logic) return;
    const old=state.localHost.alarms.get(id); if(old) clearTimeout(old);
    const h=setTimeout(()=>{
      state.localHost.alarms.delete(id);
      try{
        if(logic.gameOver || !logic._pendingAlarm || logic._nextAlarmId!==id) return;
        logic.alarm({__alarmId:id,__alarmState:logic._alarmState},id);
        state.frameRequested=true;
      }catch(e){ console.warn('[web-host] alarm',id,e); }
    },Math.max(0,Number(ms)||0));
    state.localHost.alarms.set(id,h);
  }

  function installLocalHost(logic, authoritativeOnline=false){
    // In authoritative online mode the server owns alarm execution.
    // BaseLogic still tracks _localAlarmTime/_localAlarmDuration internally for UI,
    // but the browser must NOT fire logic.alarm() on its own.
    logic.onSetAlarm=authoritativeOnline
      ? ((ms,id)=>{ if(runtimeDebug) console.debug('[SamiDev Sync] client alarm armed (server-owned)',{id,ms}); })
      : ((ms,id)=>scheduleLogicAlarm(ms,id));
    logic.onGameOver=(...args)=>{ console.log('[web-host] game over',...args); state.localHost.hotseat=false; };
    try{
      logic.onTurnChange?.receive?.(()=>{ state.frameRequested=true; });
      logic.onGameEnd?.receive?.(()=>{ state.localHost.hotseat=false; updateWebBadge(); });
    }catch(e){ console.warn('[web-host] signal hook',e); }
  }

  function cloneMove(v){ try{return structuredClone(v);}catch{ try{return JSON.parse(JSON.stringify(v));}catch{return v;} } }

  function ackLocalMove(move){
    const logic=state.gameLogic; if(!logic) return;
    const packet=cloneMove(move);
    state.localHost.moves.push(packet);
    // __info packets are client validation messages. In local mode we acknowledge them immediately.
    if(packet && packet.__info!==undefined){
      queueMicrotask(()=>{ try{logic.move(logic.localSeat??0,packet);}catch(e){console.warn('[web-host] info ack',e);} });
      return;
    }
    const pending=logic._localMoves?.[logic._localMoves.length-1];
    const seat=pending?.seat ?? logic.localSeat ?? 0;
    queueMicrotask(()=>{
      try { logic.move(seat,packet); }
      catch(e){ console.warn('[web-host] move ack',e); }
      state.frameRequested=true;
    });
  }

  function injectMove(seat,data){
    const logic=state.gameLogic; if(!logic) return false;
    const n=Array.isArray(logic._sequence)?(logic._sequence[seat]||0):0;
    const packet={i:`web-${Date.now()}-${Math.random()}`,m:cloneMove(data),n};
    try { const ok=logic.move(seat,packet); state.localHost.moves.push(packet); state.frameRequested=true; return ok; }
    catch(e){ console.warn('[web-host] inject move',seat,data,e); return false; }
  }

  function restoreStrikerVisual(logic){
    // TableView.reset() hides the striker during synchronize(). The native table API can
    // re-emit the current striker position without changing authoritative game state.
    try{
      if(!logic || logic.gameOver || !logic.started || !Array.isArray(logic.turn) || logic.turn.length===0) return;
      logic.table?.getStriKerPos?.(true);
      state.frameRequested=true;
    }catch(e){ console.warn('[web-host] striker visual restore',e); }
  }

  function synchronizeClientView(logic){
    try{ logic?.onSynchronize?.emit?.(); }
    finally{ restoreStrikerVisual(logic); }
  }

  function localResync(){
    const logic=state.gameLogic; if(!logic) return;
    // In local mode there is no upstream snapshot. Clear the resync latch and re-emit a sync
    // from the already authoritative local state instead of destroying the running match.
    try{
      logic._awaitingResync=false;
      logic._initialSync=true;
      synchronizeClientView(logic);
      state.frameRequested=true;
    }catch(e){console.warn('[web-host] resync',e);}
  }

  function followTurnIfSafe(){
    const logic=state.gameLogic;
    if(!logic || !state.localHost.hotseat || logic.gameOver || !logic.started || !Array.isArray(logic.turn) || logic.turn.length===0) return;
    const seat=logic.turn[0];
    if(!Number.isInteger(seat) || seat<0 || seat===logic.localSeat) return;
    if(logic._localMoves?.length) return;
    try{ if(logic.animator?.isAnimatingWorld?.()) return; }catch{}
    if(logic.paused) return;
    logic._localSeat=seat;
    state.localHost.currentSeat=seat;
    // Hot-seat: make the active turn look like the local player so the original input path stays intact.
    try{ typeof logic.onSync==='function' ? logic.onSync(seat) : logic.onLocalSeatUpdated?.emit?.(seat); }catch(e){ console.warn('[web-host] seat sync',e); }
    updateWebBadge();
    state.frameRequested=true;
  }

  function updateWebBadge(){
    const b=document.getElementById('web-local-badge'); if(!b) return;
    const l=state.gameLogic, seat=l?.localSeat;
    if(state.network.online){
      const room=state.network.roomId||window.SamiDevNetwork?.state?.roomId||'------';
      const connected=(state.network.roster||[]).filter(x=>x&&x.connected).length;
      const capacity=window.SamiDevNetwork?.state?.capacity||l?.seats||0;
      b.textContent=state.network.spectator?`SamiDev • ${room} • مشاهدة • ${connected}/${capacity}`:`SamiDev • ${room} • P${Number.isInteger(seat)?seat+1:1} • ${connected}/${capacity}`;
      b.style.cursor='default';
    } else {
      b.textContent=`LOCAL • P${Number.isInteger(seat)?seat+1:1}`;
      b.style.cursor='pointer';
    }
  }

  function installWebBadge(){
    if(state.network.online || new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search).get('clean')==='1') return;
    const b=document.createElement('button'); b.id='web-local-badge'; b.type='button';
    b.style.cssText='position:fixed;right:10px;bottom:10px;z-index:9999;border:0;border-radius:999px;padding:7px 10px;background:rgba(0,0,0,.62);color:#fff;font:12px system-ui;backdrop-filter:blur(6px);cursor:pointer;opacity:.82';
    b.title=state.network.online?'SamiDev Multiplayer':'وضع لاعبين محلي. اضغط للتبديل اليدوي بين المقاعد.';
    b.onclick=()=>{ if(state.network.online)return; const l=state.gameLogic;if(!l)return; const seats=Math.max(1,l.seats||2); l._localSeat=((l.localSeat??0)+1)%seats; state.localHost.currentSeat=l._localSeat; updateWebBadge(); state.frameRequested=true; };
    document.body.appendChild(b); updateWebBadge();
  }

  window.__SamiDevWebHost={injectMove, resync:localResync, setSeat:(s)=>{if(state.gameLogic){state.gameLogic._localSeat=Number(s);updateWebBadge();}}, state};

  async function waitUntilWorldSettles(logic, timeoutMs=12000){
    const started=performance.now();
    for(;;){
      let animating=false;
      try{
        // A remote shot may still be queued behind an aim/power tween.
        const queuedPoolShot=isPool && logic._queue?.some(item=>
          item.data?.[1]?.m?.a===1 || item.data?.[0]?.a===1);
        animating=!!logic.animator?.isAnimatingWorld?.() ||
          (isPool && (!!logic.preshooting || !!queuedPoolShot));
      }catch{}
      if(!animating) return true;
      if(performance.now()-started>timeoutMs){
        console.warn('[SamiDev Sync] world did not settle before timeout',{timeoutMs});
        return false;
      }
      await new Promise(r=>setTimeout(r,16));
    }
  }

  async function replayHistory(logic, history){
    if(!Array.isArray(history) || history.length===0) return true;
    for(const entry of history){
      if(!entry || !Number.isInteger(entry.seat) || !entry.packet) continue;
      const packetN=Number(entry.packet.n);
      const curSeq=Number(logic._sequence?.[entry.seat]);
      // packet.n is the pre-move sequence. If the snapshot already contains this
      // move, replaying it would manufacture a sequence mismatch and another resync.
      if(Number.isInteger(packetN) && Number.isInteger(curSeq)){
        if(packetN<curSeq) continue;
        if(packetN>curSeq){
          console.warn('[SamiDev Sync] replay gap',{seat:entry.seat,packetN,curSeq,entry});
          return false;
        }
      }
      try{
        const ok=logic.move(entry.seat, cloneMove(entry.packet));
        if(!ok){
          console.warn('[SamiDev Sync] replay move rejected',entry);
          return false;
        }
        state.frameRequested=true;
      }catch(e){
        console.warn('[SamiDev] replay move failed',entry,e);
        return false;
      }
      if(!await waitUntilWorldSettles(logic)) return false;
    }
    return true;
  }

  function applyDeferredMove(logic, msg){
    if(!msg || !Number.isInteger(msg.seat) || !msg.packet) return true;
    const packetN=Number(msg.packet.n);
    const curSeq=Number(logic._sequence?.[msg.seat]);
    // deserialize() clears optimistic local moves, so a deferred packet whose n is
    // behind the restored sequence is an already-included echo and must be ignored.
    if(Number.isInteger(packetN) && Number.isInteger(curSeq)){
      if(packetN<curSeq) return true;
      if(packetN>curSeq){
        console.warn('[SamiDev Sync] deferred move gap',{seat:msg.seat,packetN,curSeq,msg});
        return false;
      }
    }
    try{
      const ok=logic.move(msg.seat, cloneMove(msg.packet), cloneMove(msg.reveal));
      if(!ok) return false;
      state.frameRequested=true;
      return true;
    }catch(e){
      console.warn('[SamiDev Sync] deferred move failed',e,msg);
      return false;
    }
  }

  const AUTHORITY_GRACE_MS=900;
  const AUTHORITY_RETRY_MS=120;
  const AUTHORITY_MAX_WAIT_MS=5000;

  function sameNumberArray(a,b){
    if(!Array.isArray(a)||!Array.isArray(b)||a.length!==b.length) return false;
    return a.every((v,i)=>Number(v)===Number(b[i]));
  }

  function authorityMismatch(logic,msg){
    const fields=[];
    if(Array.isArray(msg?.sequence) && !sameNumberArray(msg.sequence,logic?._sequence)) fields.push('sequence');
    if(Array.isArray(msg?.turn) && !sameNumberArray(msg.turn,logic?.turn)) fields.push('turn');
    if(msg && Object.prototype.hasOwnProperty.call(msg,'gameOver') && Boolean(msg.gameOver)!==Boolean(logic?.gameOver)) fields.push('gameOver');
    return fields;
  }

  function scheduleAuthorityCheck(logic,net,msg,{ordered=false,source='authority'}={}){
    if(!msg || typeof msg!=='object') return;
    const epoch=Number(msg.authorityEpoch);
    const revision=Number(msg.revision);
    const currentPending=state.network.pendingAuthority;
    if(Number.isInteger(epoch) && Number.isInteger(revision) && currentPending &&
       Number.isInteger(currentPending.authorityEpoch) && Number.isInteger(currentPending.revision) &&
       epoch===currentPending.authorityEpoch && revision<currentPending.revision){
      return;
    }
    if(ordered && Number.isInteger(epoch) && Number.isInteger(revision)){
      if(Number.isInteger(state.network.authorityEpoch)){
        if(epoch<state.network.authorityEpoch) return;
        if(epoch>state.network.authorityEpoch){
          state.network.authorityEpoch=epoch;
          state.network.authorityRevision=-1;
        }
      } else {
        state.network.authorityEpoch=epoch;
      }
      if(revision<=state.network.authorityRevision) return;
      state.network.authorityRevision=revision;
    }
    state.network.pendingAuthority={
      turn:Array.isArray(msg.turn)?msg.turn.slice():undefined,
      sequence:Array.isArray(msg.sequence)?msg.sequence.slice():undefined,
      gameOver:Object.prototype.hasOwnProperty.call(msg,'gameOver')?Boolean(msg.gameOver):undefined,
      authorityEpoch:Number.isInteger(epoch)?epoch:undefined,
      revision:Number.isInteger(revision)?revision:undefined,
      source,
      receivedAt:performance.now(),
    };
    armAuthorityCheck(logic,net,AUTHORITY_RETRY_MS);
  }

  function armAuthorityCheck(logic,net,delay){
    if(state.network.authorityCheckTimer!==null) return;
    state.network.authorityCheckTimer=setTimeout(()=>{
      state.network.authorityCheckTimer=null;
      evaluateAuthority(logic,net);
    },Math.max(0,delay));
  }

  function evaluateAuthority(logic,net){
    const pending=state.network.pendingAuthority;
    if(!pending) return;
    const mismatch=authorityMismatch(logic,pending);
    if(mismatch.length===0){
      state.network.pendingAuthority=null;
      return;
    }
    const age=performance.now()-pending.receivedAt;
    let animating=false;
    try{ animating=!!logic.animator?.isAnimatingWorld?.() || (isPool && !!logic.preshooting); }catch{}
    const hasPendingLocal=Array.isArray(logic._localMoves)&&logic._localMoves.length>0;
    const unsafe=hasPendingLocal || !!logic._awaitingResync || state.network.snapshotBusy || animating || !!logic.paused;

    // Authority can arrive just before the matching local 500ms turn/animation timer. Give
    // normal replication a short grace period, but never discard a mismatch just because an
    // animation or optimistic local move was active when the packet arrived.
    const terminal=pending.gameOver===true && pending.source!=='move';
    if(!terminal && (age<AUTHORITY_GRACE_MS || (unsafe && age<(isPool?20000:AUTHORITY_MAX_WAIT_MS)))){
      armAuthorityCheck(logic,net,AUTHORITY_RETRY_MS);
      return;
    }

    console.warn('[SamiDev Sync] authoritative state mismatch; requesting snapshot',{
      fields:mismatch,source:pending.source,revision:pending.revision,server:{turn:pending.turn,sequence:pending.sequence,gameOver:pending.gameOver},local:{turn:logic.turn,sequence:logic._sequence,gameOver:logic.gameOver}
    });
    const sent=net.requestResync();
    if(sent){
      // Keep the mismatch until the returned authoritative snapshot is actually applied
      // and rechecked. Clearing it here would hide a stale/deferred snapshot and could leave
      // the client permanently on the wrong turn with no later revision to wake the check.
      pending.resyncRequestedAt=performance.now();
      armAuthorityCheck(logic,net,250);
    } else {
      armAuthorityCheck(logic,net,250);
    }
  }

  function installNetworkBridge(logic){
    const net=window.SamiDevNetwork;
    if(!net) throw new Error('SamiDevNetwork غير محمل');

    net.on('move', msg=>{
      // resync_state is applied asynchronously while animations settle. Queue socket
      // moves during that window so history and new live moves cannot interleave.
      if(state.network.snapshotBusy){
        state.network.deferredMoves.push(msg);
        return;
      }
      // Socket echoes can arrive after a newer authoritative snapshot. Do not
      // replay an already-consumed packet or apply an out-of-order shot.
      const packetN=Number(msg?.packet?.n);
      const expected=Number(logic._sequence?.[msg?.seat]);
      const hasSequence=Number.isInteger(packetN)&&Number.isInteger(expected);
      // Local pool/card moves increment their sequence optimistically. Their
      // matching echoes carry the pre-move sequence and may reveal private cards.
      const localMoveEcho=(isPool || isCrazy8) && msg?.seat===logic.localSeat &&
        logic._localMoves?.some(move=>move.seat===msg.seat && move.id===msg.packet?.i);
      if(hasSequence && packetN<expected && !localMoveEcho){
        if(msg?.authority) scheduleAuthorityCheck(logic,net,msg.authority,{source:'move'});
        return;
      }
      if(hasSequence && packetN>expected){
        console.warn('[SamiDev Sync] live move sequence gap',{seat:msg.seat,packetN,expected});
        net.requestResync?.();
        return;
      }
      try{
        const ok=logic.move(msg.seat, cloneMove(msg.packet), cloneMove(msg.reveal));
        if(!ok){
          console.warn('[SamiDev Sync] live move rejected; requesting authoritative snapshot',{seat:msg.seat,packetN,expected,turn:logic.turn});
          net.requestResync?.();
        }
      }catch(e){ console.warn('[SamiDev] incoming move',e,msg);net.requestResync?.(); }
      if(msg?.authority) scheduleAuthorityCheck(logic,net,msg.authority,{source:'move'});
      state.frameRequested=true;
    });

    net.on('room_state', msg=>{
      state.network.roster=msg.roster||[];
      state.network.capacity=Number(msg.capacity)||state.network.capacity||state.network.roster.length;
      applyCosmetics(msg);
      if(msg.finished && !logic.gameOver) net.requestResync();
      refreshNativeAvatars();
      updateWebBadge();
    });

    net.on('begin_match', ()=>{
      try{
        if(isCrazy8 || isPool) net.requestResync();
        if(isCarrom && logic.localSeat===0 && logic.started && (!logic.turn || logic.turn.length===0) && !logic.gameOver){
          logic.localMove({m:0});
        }
      }catch(e){ console.warn('[SamiDev] begin match',e); }
    });

    net.on('desync', msg=>{
      console.warn('[SamiDev] desync',msg);
      const b=document.getElementById('web-local-badge');
      if(b){ b.textContent='SamiDev • RESYNC'; b.style.background='rgba(150,20,20,.85)'; }
      if(!state.network.snapshotBusy) net.requestResync();
    });

    async function applyResyncState(msg){
      if(state.network.finished && !msg?.gameOver) return;
      if(state.network.snapshotBusy){
        // A terminal checkpoint can arrive during history/animation replay. Keep
        // it, rather than losing the only notification that the match has ended.
        const queued=state.network.queuedSnapshot;
        if(!queued?.gameOver || msg?.gameOver) state.network.queuedSnapshot=msg;
        return;
      }
      state.network.snapshotBusy=true;
      window.SamiDevCardAudio?.setSyncing(true);
      state.network.deferredMoves.length=0;
      let needsRetry=false;
      try{
        if(!msg || !msg.snapshot || typeof msg.snapshot!=='object') throw new Error('missing authoritative snapshot');
        // A GameHost checkpoint already contains the end of the shot. Applying
        // it during the cue tween or ball animation cancels visible movement.
        // Keep socket moves queued while presentation finishes, then reconcile.
        if(isPool){
          await waitUntilWorldSettles(logic,20000);
          if(state.network.queuedSnapshot){
            msg=state.network.queuedSnapshot;
            state.network.queuedSnapshot=null;
          }
        }
        const seat=logic.localSeat;
        applyCosmetics(msg);
        try{ logic.pause?.(); }catch(_){}
        logic.deserialize(cloneMove(msg.snapshot),seat);
        logic._initialSync=true;
        logic._awaitingResync=false;
        if(Array.isArray(msg.history)&&msg.history.length){
          const replayOk=await replayHistory(logic,msg.history);
          if(!replayOk) needsRetry=true;
        }
        if(!needsRetry){
          // Keep draining until no socket message arrived during the previous animation.
          // There is deliberately no await between observing an empty queue and releasing
          // snapshotBusy, so a live move cannot get stranded in deferredMoves.
          while(!needsRetry && !state.network.queuedSnapshot && state.network.deferredMoves.length){
            const deferred=state.network.deferredMoves.splice(0);
            for(const queued of deferred){
              if(queued.type==='authority_alarm'){ applyAuthorityAlarm(queued); continue; }
              if(!applyDeferredMove(logic,queued)){ needsRetry=true; break; }
              if(!await waitUntilWorldSettles(logic)){ needsRetry=true; break; }
            }
          }
        }
        if(!needsRetry){
          state.network.snapshotBusy=false;
          try{ await logic.resume?.(true); }catch(_){}
          try{ synchronizeClientView(logic); }catch(_){}
          if(isCrazy8 && state.unoWaitingNeedsLayout && logic.started){
            state.surface.initialized=false;resize();state.unoWaitingNeedsLayout=false;
          }
          if(isPool && !state.network.spectator) logic.sendReady?.();
          if(msg.gameOver && logic.gameOver) state.network.finished=true;
          state.frameRequested=true;
          const b=document.getElementById('web-local-badge');
          if(b){ b.style.background='rgba(0,0,0,.62)'; updateWebBadge(); }
          console.info('[SamiDev Sync] in-place resync applied',{snapshotMoveCount:msg.snapshotMoveCount,moveCount:msg.moveCount,replayed:Array.isArray(msg.history)?msg.history.length:0});
          // A live GameHost resync carries current invariants too. Replace an older pending
          // authority expectation even when its revision is equal (accepted moves do not bump
          // authorityRevision), then verify the snapshot we just applied against that state.
          if(Array.isArray(msg.turn) && Array.isArray(msg.sequence)){
            scheduleAuthorityCheck(logic,net,msg,{source:'resync_state'});
          } else if(state.network.pendingAuthority) {
            armAuthorityCheck(logic,net,AUTHORITY_RETRY_MS);
          }
        }
      }catch(e){
        needsRetry=true;
        console.warn('[SamiDev Sync] in-place resync failed',e,msg);
      }finally{
        state.network.snapshotBusy=false;
        window.SamiDevCardAudio?.setSyncing(false);
        // Do not loop synchronously. requestResync() is coalesced and only runs after
        // this application attempt has fully left the critical section.
        const queued=state.network.queuedSnapshot;
        state.network.queuedSnapshot=null;
        if(queued) await applyResyncState(queued);
        else if(needsRetry) net.requestResync();
      }
    }
    net.on('resync_state', applyResyncState);

    function applyAuthorityAlarm(msg){
      try{
        scheduleAuthorityCheck(logic,net,msg,{ordered:true,source:'authority_alarm'});
        if(state.network.spectator){
          net.requestResync();
          return;
        }
        const id=Number(msg?.alarmId);
        if(!Number.isInteger(id)) return;
        const expected=Number(logic.nextAlarmId ?? logic._nextAlarmId);
        // A valid authoritative alarm always carries the reveal generated by server BaseLogic.alarm().
        // Never pass an empty/stale authority event into client BaseLogic: that path deliberately resyncs.
        if(msg.reveal===undefined || msg.reveal===null){
          console.warn('[SamiDev Sync] ignored authority alarm without reveal',{id,expected,msg});
          return;
        }
        if(Number.isInteger(expected) && id<expected){
          console.info('[SamiDev Sync] ignored stale authority alarm',{id,expected});
          return;
        }
        const reveal=cloneMove(msg.reveal);
        const ok=logic.alarm(reveal,id);
        if(!ok && logic._pendingAlarm) console.warn('[SamiDev] authority alarm rejected',{id,expected,msg});
      }catch(e){ console.warn('[SamiDev] authority alarm',e,msg); }
      state.frameRequested=true;
    }
    net.on('authority_alarm', msg=>{
      if(state.network.snapshotBusy){
        state.network.deferredMoves.push(msg);
        scheduleAuthorityCheck(logic,net,msg,{ordered:true,source:'authority_alarm'});
        return;
      }
      applyAuthorityAlarm(msg);
    });

    net.on('disconnect', ()=>{
      const b=document.getElementById('web-local-badge');
      if(b){ b.textContent='SamiDev • DISCONNECTED'; b.style.background='rgba(150,20,20,.85)'; }
    });

    net.on('spectator_resync', ()=>{
      if(state.network.spectator) net.requestResync();
    });

    // Server-authoritative mode: clients never publish official snapshots. Compare every
    // authoritative invariant that the gateway provides, not sequence alone. The check is
    // deferred/retried while animations are active so a real mismatch can never be dropped.
    net.on('authority_state', msg=>{
      try{ scheduleAuthorityCheck(logic,net,msg,{ordered:true,source:'authority_state'}); }
      catch(e){ console.warn('[SamiDev] authority state',e); }
    });
  }

  async function prepareAssetsAndLogic(){
    state.dict = window.__dictEn || {};
    status.style.display='block';
    status.textContent='تحميل الأصول...';
    const list = [...(window.__assetImages || []), ...(isPool?['/images/themes/pool-emerald.webp','/images/cues/moon.webp']:[])];
    const selectedTheme = isCarrom && window.SamiDevCarromThemes ? await window.SamiDevCarromThemes.resolve() : null;
    state.carromTheme = selectedTheme?.id || 'carrom_classic';
    // Load the native text resources before executing main.js. Its synchronous file API
    // then reads memory instead of blocking the UI on many individual HTTP requests.
    const textPreload = (async()=>{
      if(typeof fetch!=='function') return;
      try {
        const response=await fetch('__assets.json', {credentials:'same-origin'});
        if(!response.ok) return;
        const index=await response.json();
        const paths=Object.keys(index).map(norm).filter(path=>/\.(json|atlas|txt|glsl)$/.test(path));
        window.__textAssets=window.__textAssets||{};
        window.__textAssets["__assets.json"]=JSON.stringify(index);
        let next=0;
        await Promise.all(Array.from({length:Math.min(6,paths.length)},async()=>{
          while(next<paths.length){const path=paths[next++];
            if(Object.prototype.hasOwnProperty.call(window.__textAssets,path)) continue;
            const resource=await fetch(path,{credentials:'same-origin'});
            if(resource.ok) window.__textAssets[path]=await resource.text();
          }
        }));
      }catch(e){if(runtimeDebug) console.warn('[SamiDev] text preload fallback',e);}
    })();
    await Promise.all([textPreload,...list.map(path=>new Promise(resolve=>{
      const img=new Image(); img.crossOrigin='anonymous';
      img.decoding='async';
      const themeAtlas = selectedTheme && path === 'images/game.webp';
      let fallback = false;
      img.onload=async()=>{
        let texture=img;
        if(isCarrom && path==='images/game.webp' && state.carromTheme==='carrom_classic'){
          try{
            const wood=new Image();wood.decoding='async';
            await new Promise((accept,reject)=>{wood.onload=accept;wood.onerror=reject;wood.src='/images/themes/samidev-walnut-source.png';});
            // Preserve the native atlas and all its UVs. Replace only board_0.
            // The original artwork occupies a 695px square of this source image.
            const atlas=document.createElement('canvas');atlas.width=img.width;atlas.height=img.height;
            const context=atlas.getContext('2d');context.drawImage(img,0,0);
            context.clearRect(0,0,1428,1428);
            context.drawImage(wood,0,0,695,695,0,0,1428,1428);
            texture=atlas;state.carromBoardArtwork='samidev-walnut';
          }catch(error){if(runtimeDebug)console.warn('[SamiDev] wood artwork fallback',error);}
        }
        state.images.set(norm(path),texture);resolve();
      };
      img.onerror=()=>{
        if(themeAtlas && !fallback){
          fallback=true; state.carromTheme='carrom_classic';
          img.src=window.SamiDevCarromThemes.defaultTheme.atlas; return;
        }
        console.warn('img failed',path);resolve();
      };
      const source=(isCrazy8 && path==='images/table-background.webp') ? '/games/crazy8/images/samidev-uno-felt.png' : ((window.__assetImageData && window.__assetImageData[path]) || (themeAtlas ? selectedTheme.atlas : path));
      const refreshedAsset = ['images/table-background.webp','images/ui/ui.webp','images/imported/themes/th_basic_background.webp'].includes(path);
      img.src=refreshedAsset && !source.startsWith('data:') ? source+(source.includes('?')?'&':'?')+'v=36' : source;
    }))]);
    status.textContent='تشغيل اللعبة...';
    if (!state.gameLogic) {
      await new Promise((resolve,reject)=>{ const s=document.createElement('script'); const hash=window.__SAMIDEV_CLIENT_CONFIG?.games?.[currentGame.id]?.mainJsSha256 || window.__SAMIDEV_CLIENT_CONFIG?.mainJsSha256; s.src='main.js'+(hash?`?v=${encodeURIComponent(hash.slice(0,16))}`:''); s.onload=resolve; s.onerror=()=>reject(new Error('تعذر تحميل main.js')); document.body.appendChild(s); });
    }
    if(!state.gameLogic) throw new Error('لم تسجل اللعبة GameLogic');
    return state.gameLogic;
  }

  let renderLoopStarted=false;
  function ensureRenderLoop(){if(!renderLoopStarted){renderLoopStarted=true;requestAnimationFrame(loop);}}
  async function prepareWaitingScene(message){
    const logic=await prepareAssetsAndLogic();
    const network=window.SamiDevNetwork.state;
    state.network.roomId=network.roomId;
    state.network.seat=Number(network.seat);
    state.network.roster=network.roster||message.roster||[];
    state.network.capacity=Number(network.capacity)||message.capacity;
    applyCosmetics(message);
    const nativeSettings=cloneMove(message.settings||network.settings);delete nativeSettings.gameId;
    const seats=logic.initialize(nativeSettings,state.network.seat);
    installLocalHost(logic,true);
    logic._initialSync=true;
    // No players enter, no input is installed and no ready/move is sent while
    // waiting. This is the very same native scene used when the match starts.
    state.surfaceCreated?.();
    await ensureInitialSurface();
    refreshNativeAvatars();
    ensureRenderLoop();
    window.SamiDevWaitingRoom?.sceneReady();
    return {logic,seats,settings:nativeSettings};
  }

  window.__startSamiDevGame = async function() {
    try {
      const qs=new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
      const online=qs.get('online')==='1';
      if(isCrazy8 && !online) throw new Error('أونو متاحة عبر غرف المنصة. ارجع للقائمة وأنشئ غرفة أونلاين.');
      let startData=null;
      let settings;
      let localSeat=0;
      let waitingScenePromise=null,waitingScene=null;

      if(online){
        state.network.online=true;
        state.localHost.hotseat=false;
        if(!window.SamiDevNetwork) throw new Error('SamiDev Network غير متوفر');
        state.network.waiting=true;
        window.SamiDevWaitingRoom?.show();
        const preview=message=>{
          if(!waitingScenePromise){
            waitingScenePromise=prepareWaitingScene(message);
            waitingScenePromise.catch(error=>window.SamiDevWaitingRoom?.fail(error.message));
          }else{
            state.network.roster=message.roster||state.network.roster;
            applyCosmetics(message);refreshNativeAvatars();state.frameRequested=true;
          }
        };
        const offAssignment=window.SamiDevNetwork.on('assignment',preview);
        const offRoom=window.SamiDevNetwork.on('room_state',preview);
        try{
          startData=await window.SamiDevNetwork.connectFromLocation(text=>{ if(window.SamiDevWaitingRoom){window.SamiDevWaitingRoom.progress(text);}else{status.style.display='block';status.textContent=text;} });
          if(waitingScenePromise)waitingScene=await waitingScenePromise;
        }finally{offAssignment?.();offRoom?.();}
        settings=startData.settings;
        localSeat=Number(startData.seat);
        if(!Number.isInteger(localSeat)) localSeat=-1;
        state.network.roomId=startData.roomId;
        state.network.roster=startData.roster||[];
        state.network.capacity=Number(startData.capacity)||state.network.roster.length;
        state.network.seat=localSeat;
        state.network.spectator=!!startData.spectator || localSeat<0;
        applyCosmetics(startData);
        refreshNativeAvatars();
      } else {
        settings=window.SamiDevGames.settings(qs);
      }

      const logic=await prepareAssetsAndLogic();
      window.SamiDevCardAudio?.setSyncing(true);
      if(isPool) logic.isMusicMuted=()=>true; // No ambient music recording exists in the supplied bundle.
      if(isPool && online && !logic.__samidevPoolReadyGuard){
        const nativeSendReady=logic.sendReady.bind(logic);
        logic.sendReady=()=>state.network.snapshotBusy ? false : nativeSendReady();
        logic.__samidevPoolReadyGuard=true;
      }
      if(isTableSoccer && online){
        // Automatic ball control in the supplied client moves bodies outside physics.
        // Online positions are owned by the server, so keep the physical pass result.
        logic.startControl=function(){
          this.willAnimateControl=false; this.animatingControl=false;
          this.passControlPlayer=undefined;
          this.resume(); this.sendReady();
        };
      }
      const nativeSettings=cloneMove(settings); delete nativeSettings.gameId;
      if(waitingScene && JSON.stringify(waitingScene.settings)!==JSON.stringify(nativeSettings))throw new Error('تغيّرت إعدادات الغرفة أثناء التهيئة');
      const seats=waitingScene?waitingScene.seats:logic.initialize(nativeSettings,localSeat);
      state.network.waiting=false;
      if(isCrazy8 && waitingScene)state.unoWaitingNeedsLayout=true;
      if(!waitingScene)installLocalHost(logic, online);
      logic._initialSync=true;
      try { if(!isPool) for(let seat=0;seat<seats;seat++) logic.enter?.(seat); } catch(e){console.warn('enter',e);}

      if(!waitingScene)state.surfaceCreated?.();
      await ensureInitialSurface();
      if(isPool && !online) for(let seat=0;seat<seats;seat++) logic.enter?.(seat);
      if(!state.network.spectator) installInputBridge();
      else {
        canvas.style.touchAction='none';
        canvas.style.userSelect='none';
      }
      installWebBadge();
      try { logic.resume?.(); } catch(e){console.warn('resume',e);}

      if(online){
        installNetworkBridge(logic);
        if(startData?.snapshot){
          try{
            logic.deserialize(cloneMove(startData.snapshot),localSeat);
            logic._initialSync=true;
            await replayHistory(logic,startData.history||[]);
          }catch(e){ console.warn('[SamiDev] snapshot restore failed; replaying history',e); await replayHistory(logic,startData.history||[]); }
        } else {
          await replayHistory(logic,startData?.history||[]);
        }
        try { synchronizeClientView(logic); } catch(e){console.warn('sync',e);}
        if(!state.network.spectator) window.SamiDevNetwork.runtimeReady();
      } else {
        try { synchronizeClientView(logic); } catch(e){console.warn('sync',e);}
        setTimeout(()=>{
          try{
            if(isCarrom && logic.started && (!logic.turn || logic.turn.length===0) && !logic.gameOver) injectMove(0,{m:0});
            synchronizeClientView(logic);
            followTurnIfSafe();
            restoreStrikerVisual(logic);
          }catch(e){console.warn('[local-host] first round',e);}
        },50);
      }

      window.SamiDevCardAudio?.setSyncing(false);
      status.textContent='';
      status.style.display='none';
      state.localHost.started=true;
      window.SamiDevWaitingRoom?.ready();
      ensureRenderLoop();
    } catch(e) {
      console.error(e);
      status.style.display='block';
      status.textContent='تعذر تشغيل اللعبة:\n'+String(e?.stack||e);
      window.__previewError=String(e?.stack||e);
      window.SamiDevWaitingRoom?.fail(e?.message||'تعذر تشغيل اللعبة');
    }
  };

  let renderFailureRetries=0, lastFrameTime=-Infinity;
  function loop(timestamp){
    const now=Number.isFinite(timestamp)?timestamp:performance.now();
    // 120 Hz phones must not execute twice as many complete native rendering passes.
    // Native animations and physics continue to use their own elapsed-time clock.
    if(mobileDevice && now-lastFrameTime<1000/60-1){requestAnimationFrame(loop);return;}
    lastFrameTime=now;
    try {
      flushPointerMoves();
      followTurnIfSafe();
      if(state.drawFrame && state.frameRequested){
        state.frameRequested=false;
        try {
          state.drawFrame();
          state.performance.frames++;
          renderFailureRetries=0;
        } catch (e) {
          // A transient first-frame failure used to consume the only render request, leaving
          // WebGL at its white clear color until a refresh/another event requested a frame.
          if (renderFailureRetries < 3) { renderFailureRetries++; state.frameRequested=true; }
          throw e;
        }
      }
    }
    catch(e){ console.error('render error',e); window.__renderError=String(e?.stack||e); }
    requestAnimationFrame(loop);
  }
  let resizePending=false;
  function scheduleResize(){
    if(resizePending) return;
    resizePending=true;
    requestAnimationFrame(()=>{resizePending=false;resize();});
  }
  window.addEventListener('resize',scheduleResize);
  if(typeof ResizeObserver==='function'){
    const surfaceObserver=new ResizeObserver(scheduleResize);
    surfaceObserver.observe(canvas);
  }
  canvas.addEventListener('webglcontextlost',ev=>{
    ev.preventDefault();
    status.style.display='block';
    status.textContent='تعذر الرسم مؤقتًا — استعادة WebGL...';
    window.__webglContextLost=true;
  });
  canvas.addEventListener('webglcontextrestored',()=>{
    // main.js owns GPU resources and has no context-restoration lifecycle. A clean reload is
    // safer than rendering with stale texture/buffer handles after WebGL has been recreated.
    try{ location.reload(); }catch(_){}
  });
})();
