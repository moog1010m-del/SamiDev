/* Account settings share the existing HttpOnly session; no credentials persist. */
(() => {
  'use strict';
  const $=s=>document.querySelector(s);
  let api,currentUser,signedOut,account=null,loading=0;
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
      const summary=$('#account-summary');summary.replaceChildren(node('strong',user.username),node('p',data.email||'حساب محلي','account-email'));
      const providers=(data.providers||[]).map(p=>({'google.com':'Google','password':'البريد وكلمة المرور','apple.com':'Apple'})[p]||p);
      summary.append(node('p','طريقة الدخول: '+(providers.join('، ')||'محلية'),'muted'));
      $('#account-password-reset').classList.toggle('hidden',!data.providers?.includes('password'));
      if(data.providers?.includes('google.com')&&!data.providers.includes('password'))summary.append(node('p','تُدار كلمة مرور Google من حسابك لدى Google.','muted'));
    }catch(e){if(version===loading){$('#account-summary').replaceChildren();status(e.message,true);}}
  }
  async function devices(){
    const box=$('#account-devices');box.replaceChildren(node('p','جارٍ تحميل الأجهزة…'));
    try{
      const data=await api('/api/account/devices');box.replaceChildren();
      for(const item of data.devices){
        const row=node('article','','account-device');
        const detail=node('div','');detail.append(node('strong',item.device+(item.current?' · هذا الجهاز':'')),node('p',item.client,'muted'),node('p','آخر نشاط: '+stamp(item.lastSeenAt),'muted'));
        let country='غير متاح';try{if(item.country)country=new Intl.DisplayNames(['ar'],{type:'region'}).of(item.country);}catch(_){}
        detail.append(node('p','الموقع التقريبي: '+country,'muted'));
        const button=node('button','تسجيل الخروج','danger-btn');button.type='button';button.dataset.deviceId=item.id;
        button.onclick=()=>run(button,async()=>{if(!confirm(item.current?'سيتم تسجيل خروجك من هذا الجهاز. متابعة؟':'تسجيل الخروج من هذا الجهاز؟'))return;const result=await api('/api/account/devices/'+encodeURIComponent(item.id),{method:'DELETE'});if(result.signedOut)await signedOut();else await devices();});
        row.append(detail,button);box.append(row);
      }
      if(!data.devices.length)box.append(node('p','لا توجد جلسات نشطة.'));
    }catch(e){box.replaceChildren(node('p','تعذر تحميل الأجهزة. أعد المحاولة.'));status(e.message,true);}
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
    ({api,currentUser,signedOut}=options);
    $('#account-password-reset').onclick=event=>run(event.currentTarget,async()=>{if(!account?.providers?.includes('password'))return;await window.SamiDevFirebaseAuth.resetPassword(account.email);status('أرسلنا رابط تغيير كلمة المرور إلى بريد حسابك. بعد التغيير ستنتهي جلسات الدخول السابقة.');});
    $('#account-devices-refresh').onclick=devices;
    $('#account-logout-all').onclick=event=>run(event.currentTarget,async()=>{if(!confirm('تسجيل الخروج من جميع الأجهزة، بما فيها هذا الجهاز؟'))return;await api('/api/account/logout-all',{method:'POST',body:'{}'});await signedOut();});
    $('#account-delete').onclick=deletion;
    $('#account-settings-btn').onclick=()=>{$('#settings-auth-slot').classList.toggle('hidden');};
  }};
})();
