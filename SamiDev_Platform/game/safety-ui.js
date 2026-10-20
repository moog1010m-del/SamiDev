/* Shared block/report sheet. Reasons and user text never become executable HTML. */
(()=>{'use strict';
 const reasons=[['harassment','هذا الشخص يضايقني أو يتنمر.'],['cheating','هذا الشخص يغش في اللعب.'],['abuse','إساءة أو خطاب كراهية.'],['profile','اسم المستخدم أو الصورة غير لائقين.'],['threat','تهديد بالعنف في الحياة الواقعية.'],['exploitation','استغلال أو تحرش جنسي.'],['spam','رسائل مزعجة أو احتيال.'],['other','سبب آخر.']];
 let active=null;
 function open({api,user,roomId='',onChanged=()=>{},toast=()=>{}}){
  if(active||!user?.id)return;
  const prior=document.activeElement,d=document.createElement('dialog');active=d;d.className='plazr-safety';d.dir='rtl';d.setAttribute('aria-labelledby','plazr-safety-title');
  const make=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
  const title=make('h2','الحظر والإبلاغ');title.id='plazr-safety-title';const close=make('button','إغلاق');close.type='button';close.onclick=()=>d.close();
  const name=make('strong',user.username||'المستخدم'),hint=make('p','الحظر يخفي رسائله ويمنع طلبات الصداقة. لا يغيّر مباراة قائمة.');
  const label=make('p','اختر سببًا'),list=make('div');list.className='plazr-safety-reasons';let selected=null;
  const detail=make('textarea');detail.maxLength=500;detail.rows=3;detail.placeholder='تفاصيل إضافية (اختياري)';detail.setAttribute('aria-label','تفاصيل البلاغ');
  const check=make('input');check.type='checkbox';check.checked=true;const blockLabel=make('label');blockLabel.append(check,make('span','حظر المستخدم أيضًا'));
  const status=make('p');status.setAttribute('role','status');const send=make('button','إرسال البلاغ'),only=make('button','حظر فقط');send.disabled=true;
  const controls=[];
  for(const [id,text]of reasons){const b=make('button',text);b.type='button';b.dataset.reason=id;b.setAttribute('aria-pressed','false');b.onclick=()=>{selected=id;controls.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));send.disabled=false;};controls.push(b);list.append(b);}
  let busy=false;async function submit(report){if(busy||report&&!selected)return;busy=true;[send,only,close,...controls,check,detail].forEach(x=>x.disabled=true);status.textContent='جارٍ الإرسال…';
   try{const result=await api('/api/users/'+encodeURIComponent(user.id)+(report?'/report':'/block'),{method:'POST',body:JSON.stringify(report?{reason:selected,message:detail.value,roomId,block:check.checked}:{blocked:true})});
    onChanged(result.blocked===true);toast(report?(result.blocked?'تم الحظر وإرسال البلاغ للإدارة':'تم إرسال البلاغ للإدارة'):'تم حظر المستخدم');d.close();
   }catch(e){status.textContent=e.message||'تعذر تنفيذ الطلب؛ أعد المحاولة';busy=false;[send,only,close,...controls,check,detail].forEach(x=>x.disabled=false);send.disabled=!selected;}}
  send.onclick=()=>submit(true);only.onclick=()=>submit(false);const actions=make('div');actions.className='plazr-safety-actions';actions.append(send,only);d.append(close,title,name,hint,label,list,detail,blockLabel,status,actions);
  d.addEventListener('cancel',e=>{if(busy)e.preventDefault();});d.addEventListener('close',()=>{d.remove();active=null;prior?.focus?.();},{once:true});document.body.append(d);d.showModal();close.focus();
 }
 const style=document.createElement('style');style.textContent='.plazr-safety{box-sizing:border-box;width:min(540px,calc(100vw - 24px));max-height:90dvh;overflow:auto;border:1px solid #ffffff25;border-radius:20px;background:#15191c;color:#eef4f6;padding:22px;font:15px/1.7 system-ui}.plazr-safety::backdrop{background:#0008}.plazr-safety h2{font-size:20px;margin:10px 0}.plazr-safety p{font-size:13px;color:#b9c6cb}.plazr-safety button{font:inherit;color:inherit;cursor:pointer;background:#263239;border:1px solid #ffffff20;border-radius:10px;padding:10px 16px;margin:4px}.plazr-safety button:disabled{opacity:.5;cursor:default}.plazr-safety-reasons{display:grid;gap:3px;margin-bottom:16px}.plazr-safety-reasons button{text-align:right;margin:0;border-radius:0;background:transparent;border-width:0 0 1px;padding:14px 4px}.plazr-safety-reasons button[aria-pressed=true]{background:#227d8838;color:#7ce4e4}.plazr-safety textarea{box-sizing:border-box;width:100%;background:#20282d;color:inherit;border:1px solid #53656e;border-radius:10px;padding:12px;font:inherit}.plazr-safety label{display:flex;align-items:center;gap:10px;margin-top:12px}html[data-theme=light] .plazr-safety{background:#fff;color:#1e3038}html[data-theme=light] .plazr-safety p{color:#53656e}html[data-theme=light] .plazr-safety button{background:#eaf1f3;color:#1e3038}html[data-theme=light] .plazr-safety textarea{background:#f6f9fa;color:#1e3038}.plazr-safety-actions{position:sticky;bottom:-22px;background:inherit;padding:10px 0;display:flex;gap:8px}.plazr-safety-actions button{flex:1}html[data-theme=light] .plazr-safety-reasons button{background:transparent;border-color:#dce6e9}html[data-theme=light] .plazr-safety-reasons button[aria-pressed=true]{background:#d7f2ef;color:#145c60;box-shadow:inset -3px 0 #247d83}';document.head.append(style);
 window.PlazrSafety={open,reasons};
})();
