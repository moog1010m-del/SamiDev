/* Public self-service deletion: fresh provider proof, no app-session switch. */
(() => {
  'use strict';
  const $=s=>document.querySelector(s);
  let config=null,proof=null,busy=false,googleModule=null;
  const status=message=>{$('#deletion-status').textContent=message;};
  const controls=()=>{for(const node of document.querySelectorAll('form input,button'))node.disabled=busy;$('#public-delete-confirm').disabled=busy||!proof||!$('#public-delete-ack').checked;};
  function clear(){proof=null;$('#public-delete-password').value='';$('#public-delete-ack').checked=false;$('#deletion-confirmation').hidden=true;controls();}
  async function verified(token){
    clear();
    if(typeof token!=='string'||!token)throw Error('لم تصل هوية صالحة. حاول مجددًا.');
    const response=await fetch('/api/account/deletion-preview',{method:'POST',credentials:'omit',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({idToken:token}),signal:AbortSignal.timeout(20000)});
    const data=await response.json();
    if(!response.ok||!data.ok)throw Error(data.message||'تعذر تأكيد حسابك. حاول مجددًا.');
    proof=token;$('#deletion-account-name').textContent=data.username+' · '+data.email;$('#deletion-confirmation').hidden=false;
    status('تم تأكيد الدخول. راجع الحساب والبيانات التي ستُحذف ثم أكد الحذف نهائيًا.');
  }
  async function run(action){if(busy)return;busy=true;controls();try{await action();}catch(e){status(e.message||'تعذر إكمال الطلب. حاول مجددًا.');}finally{busy=false;controls();}}
  $('#public-delete-ack').onchange=controls;
  $('#public-delete-email-form').onsubmit=event=>{event.preventDefault();run(async()=>{
    clear();
    const response=await fetch('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key='+encodeURIComponent(config.apiKey),{method:'POST',credentials:'omit',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#public-delete-email').value.trim(),password:$('#public-delete-password').value,returnSecureToken:true}),signal:AbortSignal.timeout(20000)});
    $('#public-delete-password').value='';
    const data=await response.json();
    if(!response.ok)throw Error('تعذر تأكيد الدخول. تحقق من البريد وكلمة المرور، أو استخدم Google إذا كان حسابك مرتبطًا به.');
    await verified(data.idToken);
  });};
  $('#public-delete-google').onclick=()=>run(async()=>{clear();await verified((await (await googleModule).authenticateGoogle(config)).idToken);});
  $('#public-delete-confirm').onclick=()=>run(async()=>{
    if(!proof||!$('#public-delete-ack').checked)return;
    const response=await fetch('/api/account/delete',{method:'POST',credentials:'omit',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({idToken:proof,confirm:'DELETE'}),signal:AbortSignal.timeout(25000)});
    const data=await response.json();clear();
    if(!response.ok||!data.ok)throw Error(data.message||'تعذر حذف الحساب. أكد الدخول مجددًا ثم حاول.');
    $('#public-deletion-auth').hidden=true;
    status(data.pending?'تم استلام طلب الحذف وإيقاف الحساب. سيُستكمل الحذف تلقائيًا عند عودة خدمة المصادقة.':'حُذف حساب SamiDev وبياناته. لم يُحذف حساب Google الشخصي.');
  });
  window.addEventListener('pagehide',clear);
  busy=true;controls();
  fetch('/api/auth/config',{credentials:'omit',redirect:'error',signal:AbortSignal.timeout(15000)}).then(async response=>{
    if(!response.ok)throw Error('تعذر تحميل إعدادات المصادقة. أعد تحميل الصفحة.');
    config=await response.json();
    if(config.provider!=='firebase'||!config.apiKey){$('#public-deletion-auth').hidden=true;status('افتح إعدادات الحساب أدناه لحذف الحساب المحلي.');return;}
    googleModule=import('/platform/vendor/google-auth.js');
    await googleModule;busy=false;controls();
  }).catch(error=>status(error.message||'تعذر الاتصال بخدمة المصادقة. أعد تحميل الصفحة.'));
})();
