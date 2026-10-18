(() => {
  'use strict';
  const button=document.querySelector('#admin-bots-open');
  if(!button)return;
  let dialog=null,state=null,selected=null;
  const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(path,options={}){
    const response=await fetch('/api/admin/bots'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json'}});
    const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.message||'تعذر تنفيذ الطلب');return result;
  }
  const status=(text,error=false)=>{const box=dialog?.querySelector('[data-status]');if(box){box.textContent=text;box.dataset.error=String(error);}};
  const roomOptions=()=>state.communities.map(c=>`<option value="${e(c.id)}">${e(c.name)}</option>`).join('');
  function drawList(){
    const filter=dialog.querySelector('[name=filterRoom]').value,query=dialog.querySelector('[name=search]').value.trim().toLowerCase();
    const list=state.bots.filter(u=>(!filter||u.room===filter)&&(!query||[u.username,u.bio].join(' ').toLowerCase().includes(query)));
    dialog.querySelector('[data-total]').textContent=`${list.length} / ${state.bots.length}`;
    dialog.querySelector('[data-list]').innerHTML=list.map(u=>`<button type="button" class="bot-admin-row ${selected===u.id?'selected':''}" data-bot="${e(u.id)}"><img src="${u.avatarUrl?e(u.avatarUrl):'/platform/assets/brand/app-icon.svg'}" alt="" width="40" height="40"><span><strong>${e(u.username)}</strong><small>${e(state.communities.find(c=>c.id===u.room)?.name||u.room)} · ${u.online?'متصل':'غير متصل'}</small></span><span class="bot-admin-dot" data-online="${u.online?'1':'0'}"></span></button>`).join('')||'<p class="bot-admin-empty">لا توجد حسابات مطابقة.</p>';
    dialog.querySelectorAll('[data-bot]').forEach(b=>b.onclick=()=>selectBot(b.dataset.bot));
  }
  function selectBot(id){
    selected=id;const user=state.bots.find(u=>u.id===id),form=dialog.querySelector('[data-editor]');
    form.hidden=!user;if(!user)return;
    for(const key of ['username','bio','room','skill'])form.elements.namedItem(key).value=user[key]||'';
    form.elements.namedItem('enabled').checked=user.enabled;
    form.elements.namedItem('badgeId').value=user.nameBadge||'';
    form.elements.namedItem('avatar').value='';form.elements.namedItem('clearAvatar').checked=false;
    form.querySelector('[data-presence]').textContent=user.presenceError?`الاتصال متعذر: ${user.presenceError}`:user.online?'متصل داخل المساحة':'غير متصل';
    drawList();
  }
  async function refresh(){
    state=await api('');
    dialog.querySelector('.bot-admin-note').textContent=state.gameplayReady?'عامل البلياردو متصل؛ يدخل الطاولات المنتظرة حسب إعداداته.':'عامل البلياردو غير متصل حاليًا. الحسابات والحضور يعملان بصورة مستقلة.';
    drawList();if(selected)selectBot(selected);
  }
  async function act(button,fn){
    button.disabled=true;status('جارٍ التنفيذ…');
    try{const message=await fn();await refresh();status(message||'تم الحفظ');}
    catch(error){status(error.message,true);}
    finally{button.disabled=false;}
  }
  async function open(){
    if(dialog)return;
    dialog=document.createElement('dialog');dialog.className='bot-admin-dialog';dialog.dir='rtl';dialog.setAttribute('aria-labelledby','bot-admin-title');
    dialog.innerHTML=`<header><div><h2 id="bot-admin-title">إدارة اللاعبين الآليين</h2><p>حسابات محفوظة ومستقلة لكل مساحة.</p></div><button type="button" data-close aria-label="إغلاق">×</button></header><p class="bot-admin-note">التحكم بالحسابات والحضور متاح. عامل البلياردو منفصل ويمكن إيقافه دون تعطيل المنصة.</p><div class="bot-admin-tools"><button type="button" data-provision>تجهيز 50 حسابًا لكل روم</button><label>إضافة لروم <select name="addRoom"></select></label><label>العدد <input name="addCount" type="number" min="1" max="50" value="1"></label><button type="button" data-add>إضافة</button><button type="button" data-refresh>تحديث</button></div><div class="bot-admin-filters"><input name="search" placeholder="بحث باليوزر" aria-label="بحث باليوزر"><select name="filterRoom" aria-label="تصفية حسب الروم"></select><span data-total></span><button type="button" data-bulk="1">توصيل حسابات الروم</button><button type="button" data-bulk="0">فصل حسابات الروم</button></div><div class="bot-admin-content"><div data-list class="bot-admin-list" aria-label="الحسابات"></div><form data-editor hidden><label>اسم المستخدم <input name="username" dir="ltr" minlength="3" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" required></label><label>البايو <textarea name="bio" maxlength="160" rows="2"></textarea></label><label>الروم <select name="room"></select></label><label>مهارة اللعب المستهدفة <select name="skill"><option value="beginner">مبتدئ</option><option value="medium">متوسط</option><option value="expert">محترف</option></select></label><label>الشارة <select name="badgeId"></select></label><label>أفتار أو شعار <input type="file" name="avatar" accept="image/png,image/jpeg,image/webp"></label><label class="bot-admin-check"><input type="checkbox" name="clearAvatar">إزالة الصورة الحالية</label><label class="bot-admin-check"><input type="checkbox" name="enabled">تفعيل الاتصال</label><small data-presence></small><button type="submit">حفظ الحساب</button></form></div><footer><p data-status role="status">جارٍ تحميل الحسابات…</p></footer>`;
    document.body.append(dialog);dialog.showModal();
    const close=()=>dialog?.close();dialog.querySelector('[data-close]').onclick=close;
    dialog.addEventListener('close',()=>{dialog.remove();dialog=null;selected=null;button.focus();},{once:true});
    dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();});
    try{
      state=await api('');
      dialog.querySelector('.bot-admin-note').textContent=state.gameplayReady?'عامل البلياردو متصل؛ يدخل الطاولات المنتظرة حسب إعداداته.':'عامل البلياردو غير متصل حاليًا. الحسابات والحضور يعملان بصورة مستقلة.';
      dialog.querySelector('[name=addRoom]').innerHTML=roomOptions();dialog.querySelector('[name=room]').innerHTML=roomOptions();
      dialog.querySelector('[name=filterRoom]').innerHTML='<option value="">كل الرومات</option>'+roomOptions();
      dialog.querySelector('[name=badgeId]').innerHTML='<option value="">بدون شارة</option>'+state.badges.map(b=>`<option value="${e(b.id)}">${e(b.name)}</option>`).join('');
      dialog.querySelector('[name=filterRoom]').onchange=drawList;dialog.querySelector('[name=search]').oninput=drawList;
      dialog.querySelector('[data-refresh]').onclick=event=>act(event.currentTarget,refresh);
      dialog.querySelector('[data-provision]').onclick=event=>act(event.currentTarget,async()=>{const result=await api('',{method:'POST',body:JSON.stringify({targetPerRoom:50,enabled:true})});return `أضيف ${result.created} حسابًا. الحسابات الموجودة محفوظة.`;});
      dialog.querySelector('[data-add]').onclick=event=>act(event.currentTarget,async()=>{const result=await api('',{method:'POST',body:JSON.stringify({room:dialog.querySelector('[name=addRoom]').value,addCount:Number(dialog.querySelector('[name=addCount]').value),enabled:true})});return `أضيف ${result.created} حسابًا.`;});
      dialog.querySelectorAll('[data-bulk]').forEach(control=>control.onclick=event=>act(event.currentTarget,async()=>{const room=dialog.querySelector('[name=filterRoom]').value;const result=await api('',{method:'PATCH',body:JSON.stringify({enabled:control.dataset.bulk==='1',...(room?{room}:{})})});return `تم تحديث ${result.updated} حسابًا حسب الروم المحدد؛ البحث النصي لا يحدد الحسابات.`;}));
      dialog.querySelector('[data-editor]').onsubmit=event=>{event.preventDefault();const form=event.currentTarget,id=selected;
        act(form.querySelector('[type=submit]'),async()=>{
          const body=Object.fromEntries(['username','bio','room','skill','badgeId'].map(k=>[k,form.elements.namedItem(k).value]));body.enabled=form.elements.namedItem('enabled').checked;
          const file=form.elements.namedItem('avatar').files[0];
          if(file){
            if(file.size>300000)throw new Error('اختر صورة أقل من 300 كيلوبايت.');
            body.avatarData=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('تعذر قراءة الصورة'));reader.readAsDataURL(file);});
          }else if(form.elements.namedItem('clearAvatar').checked)body.avatarData='';
          await api('/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify(body)});return 'تم حفظ الحساب';
        });
      };
      drawList();status('اختر حسابًا لتعديله، أو جهّز الحسابات للرومات.');
    }catch(error){status(error.message,true);}
  }
  button.addEventListener('click',open);
})();
