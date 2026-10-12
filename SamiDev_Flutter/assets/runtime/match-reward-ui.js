/* Brief completion notice. Wallet changes are accepted only by the backend. */
(() => {
  'use strict';
  const seen=new Set();
  let timer,notice;
  function dismiss(){clearTimeout(timer);notice?.remove();notice=null;}
  function show(reward){
    if(!reward?.id||seen.has(reward.id))return;
    seen.add(reward.id);if(seen.size>100)seen.delete(seen.values().next().value);
    const amount=Math.max(0,Number(reward.amount)||0);
    const done=Math.max(0,Number(reward.rewardedMatches)||0),remaining=Math.max(0,Number(reward.remainingMatches)||0);
    dismiss();
    notice=document.createElement('aside');notice.id='sd-match-reward';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
    const icon=document.createElement('span');icon.className='sd-reward-coin';icon.textContent='✦';icon.setAttribute('aria-hidden','true');
    const copy=document.createElement('div'),title=document.createElement('strong'),detail=document.createElement('small');
    title.textContent=amount?`+${amount.toLocaleString('ar-SA')} كوينز`:'اكتملت مكافآت اليوم';
    detail.textContent=amount?`مكافأة المباراة · تحدي اليوم ${done}/${done+remaining}`:'مباراة مكتملة · ارجع غدًا لمكافآت جديدة';
    copy.append(title,detail);
    const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','إغلاق إشعار المكافأة');close.onclick=dismiss;
    notice.append(icon,copy,close);document.body.append(notice);
    timer=setTimeout(dismiss,5500);
  }
  const style=document.createElement('style');style.textContent=`
    #sd-match-reward{position:fixed;z-index:11000;top:calc(env(safe-area-inset-top) + 88px);left:50%;transform:translateX(-50%);width:max-content;max-width:calc(100vw - 32px);box-sizing:border-box;display:flex;align-items:center;gap:12px;padding:12px 15px;border:1px solid #8f7136;border-radius:16px;background:rgba(17,25,28,.96);color:#f7e6be;box-shadow:0 8px 30px #0005;direction:rtl;font-family:system-ui,sans-serif;animation:sdRewardAppear .2s ease-out}
    #sd-match-reward>div{display:grid;gap:4px;min-width:0}#sd-match-reward strong{font-size:15px}#sd-match-reward small{font-size:11px;color:#c1baab}#sd-match-reward button{border:0;background:none;color:#d6cbaa;font-size:22px;padding:2px 5px;cursor:pointer}.sd-reward-coin{width:32px;height:32px;border-radius:50%;display:grid;place-items:center;background:#d9ad53;color:#392b12;font-size:20px;flex:0 0 auto}
    @keyframes sdRewardAppear{from{opacity:0;translate:0 -6px}to{opacity:1;translate:0 0}}
    @media(prefers-reduced-motion:reduce){#sd-match-reward{animation:none}}
  `;document.head.append(style);
  window.SamiDevNetwork?.on('match_reward',show);
  window.SamiDevNetwork?.on('left_room',dismiss);
})();
