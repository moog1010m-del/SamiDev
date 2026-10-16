/* Account settings share the existing HttpOnly session; no credentials persist. */
(() => {
  'use strict';
  const $=s=>document.querySelector(s);
  let api,currentUser,signedOut,onUserChanged,account=null,loading=0;
  const node=(tag,text,className='')=>{const n=document.createElement(tag);n.textContent=text;n.className=className;return n;};
  const status=(message,error=false)=>{const n=$('#account-security-status');n.textContent=message;n.classList.toggle('error',error);};
  const stamp=value=>value?new Date(value).toLocaleString('ar-SA',{dateStyle:'medium',timeStyle:'short'}):'غير متاح للجلسات القديمة';
  async function run(button,action){if(button.disabled)return;button.disabled=true;status('');try{await action();}catch(e){status(e.message||'تعذر إكمال الطلب. حاول مجددًا.',true);}finally{button.disabled=false;}}
  function reset(){account=null;loading++;$('#account-summary').replaceChildren();$('#account-password-reset').classList.add('hidden');$('#account-delete').disabled=true;}
  async function show(tab){
    status('');
    if(tab==='devices')return devices();
    if(tab!=='account')return;
    reset();const user=currentUser(),guest=user?.isGuest===true,version=loading;
    $('#settings-account-state').textContent=guest?'تلعب كضيف. اربط حسابك لحفظ تقدمك والوصول إليه من جهاز آخر.':'إدارة حسابك وأمان الدخول.';
    $('#account-settings-btn').classList.toggle('hidden',!guest);
    $('#settings-auth-slot').classList.add('hidden');
    $('#account-saved').classList.toggle('hidden',guest);
    $('#account-delete').disabled=false;
    if(guest)return;
    $('#account-summary').append(node('p','جارٍ تحميل بيانات الحساب…','muted'));
    try{
      const data=await api('/api/account');if(version!==loading||user.id!==currentUser()?.id)return;
      account=data;
      const summary=$('#account-summary');const avatar=document.createElement('img');avatar.className='settings-account-avatar';avatar.alt='';avatar.src=user.avatarData||'/images/default-avatar.png';
      summary.replaceChildren(avatar,node('strong',user.username),node('p',data.email||'حساب محلي','account-email'));
      $('#settings-username-value').textContent=user.username;$('#settings-rename-credit').textContent=user.freeRenameAvailable?'تغيير الاسم مجاني مرة واحدة. اختر اسمك عندما تكون مستعدًا.':'بطاقات تغيير الاسم: '+(user.renameCredits||0);
      const providers=(data.providers||[]).map(p=>({'google.com':'Google','password':'البريد وكلمة المرور','apple.com':'Apple'})[p]||p);
      summary.append(node('p','طريقة الدخول: '+(providers.join('، ')||'محلية'),'settings-account-provider'));
      $('#account-password-reset').classList.toggle('hidden',!data.providers?.includes('password'));
      if(data.providers?.includes('google.com')&&!data.providers.includes('password'))summary.append(node('p','تُدار كلمة مرور Google من حسابك لدى Google.','muted'));
    }catch(e){if(version===loading){$('#account-summary').replaceChildren();status(e.message,true);}}
  }
  async function devices(){
    const box=$('#account-devices');box.replaceChildren(node('p','جارٍ تحميل الأجهزة…'));
    try{
      const data=await api('/api/account/devices');box.replaceChildren();
      for(const item of data.devices){
        const row=node('article','','account-device'),button=node('button','','settings-device-row');button.type='button';
        button.dataset.deviceId=item.id;button.setAttribute('aria-label','تفاصيل '+item.device);
        const badge=node('span','','settings-device-icon '+platform(item));badge.append(icon(platform(item)==='desktop'?'devices':'phone'));
        const detail=node('span','');detail.append(node('strong',item.device+(item.current?' · هذا الجهاز':'')),node('p',item.client));
        const arrow=node('span','‹','settings-chevron');arrow.setAttribute('aria-hidden','true');
        button.append(badge,detail,arrow);button.onclick=()=>deviceDetails(item);row.append(button);box.append(row);
      }
      if(!data.devices.length)box.append(node('p','لا توجد جلسات نشطة.'));
    }catch(e){box.replaceChildren(node('p','تعذر تحميل الأجهزة. أعد المحاولة.'));status(e.message,true);}
  }
  function platform(item){return /Android/i.test(item.device)?'android':/iPhone|iPad|Mac/i.test(item.device)?'apple':'desktop';}
  const paths={account:['M20 21v-2a7 7 0 0 0-14 0v2','M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],devices:['M3 3h18v13H3z','M8 21h8M12 16v5'],phone:['M7 2h10v20H7z','M11 18h2'],appearance:['M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h4a5 5 0 0 0 5-5c0-3-4-5-9-5','M7 8h.01M7 13h.01M12 6h.01M17 8h.01'],notifications:['M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9','M10 21h4'],privacy:['M5 10h14v11H5z','M8 10V6a4 4 0 0 1 8 0v4']};
  function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');for(const d of paths[name]||paths.devices){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);svg.append(path);}return svg;}
  function country(item){try{return item.country?new Intl.DisplayNames(['ar'],{type:'region'}).of(item.country):'غير متاح';}catch(_){return 'غير متاح';}}
  function deviceDetails(item){
    const dialog=$('#settings-device-dialog');$('#settings-device-title').textContent=item.device;$('#settings-device-current').textContent=item.current?'هذا الجهاز':'';
    const badge=$('#settings-device-icon');badge.replaceChildren(icon(platform(item)==='desktop'?'devices':'phone'));
    const rows=$('#settings-device-information');rows.replaceChildren();
    for(const [label,value] of [['طريقة الاتصال',item.client],['آخر نشاط',stamp(item.lastSeenAt)],['الموقع التقريبي',country(item)]]){const row=node('div','');row.append(node('dt',label),node('dd',value));rows.append(row);}
    $('#settings-device-error').textContent='';
    $('#settings-device-close').onclick=()=>dialog.close();
    $('#settings-device-signout').onclick=async event=>{
      const button=event.currentTarget;if(button.disabled)return;button.disabled=true;$('#settings-device-close').disabled=true;$('#settings-device-error').textContent='';
      const block=e=>e.preventDefault();dialog.addEventListener('cancel',block);
      try{const result=await api('/api/account/devices/'+encodeURIComponent(item.id),{method:'DELETE'});dialog.close();if(result.signedOut)await signedOut();else await devices();}
      catch(e){$('#settings-device-error').textContent=e.message||'تعذر تسجيل خروج الجهاز. حاول مجددًا.';}
      finally{button.disabled=false;$('#settings-device-close').disabled=false;dialog.removeEventListener('cancel',block);}
    };
    dialog.showModal();
  }
  function rename(){
    const dialog=$('#settings-rename-dialog'),user=currentUser();$('#settings-rename-input').value=user.username;$('#settings-rename-error').textContent='';$('#settings-rename-note').textContent=user.freeRenameAvailable?'هذا التغيير مجاني.':'ستُستهلك بطاقة تغيير اسم واحدة عند الحفظ.';
    $('#settings-rename-cancel').onclick=()=>dialog.close();
    $('#settings-rename-form').onsubmit=async event=>{
      event.preventDefault();const button=$('#settings-rename-save');if(button.disabled)return;button.disabled=true;$('#settings-rename-cancel').disabled=true;
      const block=e=>e.preventDefault();dialog.addEventListener('cancel',block);
      try{const result=await api('/api/profile',{method:'PATCH',body:JSON.stringify({username:$('#settings-rename-input').value.trim()})});onUserChanged(result.user);dialog.close();await show('account');}
      catch(e){$('#settings-rename-error').textContent=e.message||'تعذر حفظ الاسم. حاول مجددًا.';}
      finally{button.disabled=false;$('#settings-rename-cancel').disabled=false;dialog.removeEventListener('cancel',block);}
    };
    dialog.showModal();$('#settings-rename-input').focus();
  }
  async function deletion(){
    if(!currentUser()?.isGuest&&!account){status('افتح تبويب الحساب وانتظر تحميل بياناته أولًا.',true);return;}
    const dialog=$('#delete-account-dialog'),form=$('#delete-account-form'),error=$('#delete-account-error');
    form.reset();error.textContent='';
    const guest=currentUser()?.isGuest===true,google=account?.providers?.includes('google.com'),password=account?.providers?.includes('password');
    $('#delete-current-password').classList.toggle('hidden',guest||google);
    $('#delete-password').required=!guest&&!google;
    $('#delete-reauth-note').textContent=guest?'سيُحذف حساب الضيف وتقدمه نهائيًا.':google?'سيُطلب منك تأكيد نفس حساب Google قبل الحذف.':'أدخل كلمة المرور الحالية لتأكيد هويتك.';
    dialog.showModal();$('#delete-cancel').onclick=()=>dialog.close();
    form.onsubmit=async event=>{
      event.preventDefault();const button=$('#delete-confirm');if(button.disabled)return;button.disabled=true;$('#delete-cancel').disabled=true;error.textContent='';
      const block=e=>e.preventDefault();dialog.addEventListener('cancel',block);
      try{
        const body={confirm:'DELETE'};
        if(!guest){
          if(google||password)body.idToken=await window.SamiDevFirebaseAuth.reauthenticate({google,email:account.email,password:$('#delete-password').value});
          else body.password=$('#delete-password').value;
        }
        $('#delete-password').value='';
        const result=await api('/api/account/delete',{method:'POST',body:JSON.stringify(body)});
        dialog.close();await signedOut();
        alert(result.pending?'تم استلام طلب الحذف وإيقاف الحساب. سيُستكمل الحذف تلقائيًا عند عودة خدمة المصادقة.':'حُذف الحساب وبياناته من المنصة.');
      }catch(e){error.textContent=e.message||'تعذر تأكيد الهوية. أعد المحاولة.';}
      finally{button.disabled=false;$('#delete-cancel').disabled=false;dialog.removeEventListener('cancel',block);$('#delete-password').value='';}
    };
  }
  window.SamiDevAccountSettings={show,init(options){
    ({api,currentUser,signedOut,onUserChanged}=options);
    for(const el of document.querySelectorAll('[data-settings-icon]'))el.replaceChildren(icon(el.dataset.settingsIcon));
    $('#settings-rename').onclick=rename;
    $('#account-password-reset').onclick=event=>run(event.currentTarget,async()=>{if(!account?.providers?.includes('password'))return;await window.SamiDevFirebaseAuth.resetPassword(account.email);status('أرسلنا رابط تغيير كلمة المرور إلى بريد حسابك. بعد التغيير ستنتهي جلسات الدخول السابقة.');});
    $('#account-devices-refresh').onclick=devices;
    $('#account-logout-all').onclick=event=>run(event.currentTarget,async()=>{if(!confirm('تسجيل الخروج من جميع الأجهزة، بما فيها هذا الجهاز؟'))return;await api('/api/account/logout-all',{method:'POST',body:'{}'});await signedOut();});
    $('#account-delete').onclick=deletion;
    $('#account-settings-btn').onclick=()=>{$('#settings-auth-slot').classList.toggle('hidden');};
  }};
})();
