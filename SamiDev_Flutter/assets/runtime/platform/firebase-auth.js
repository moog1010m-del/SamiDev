/* Email REST + the locally bundled official Firebase popup flow. */
(() => {
  'use strict';
  let idToken=null,refreshToken=null,key=null;
  const messages={EMAIL_EXISTS:'البريد مستخدم بالفعل. سجّل الدخول أو استعد كلمة المرور.',INVALID_EMAIL:'أدخل بريدًا إلكترونيًا صالحًا.',INVALID_LOGIN_CREDENTIALS:'البريد أو كلمة المرور غير صحيحة.',EMAIL_NOT_FOUND:'البريد أو كلمة المرور غير صحيحة.',INVALID_PASSWORD:'البريد أو كلمة المرور غير صحيحة.',TOO_MANY_ATTEMPTS_TRY_LATER:'محاولات كثيرة؛ حاول لاحقًا.',USER_DISABLED:'هذا الحساب موقوف.',WEAK_PASSWORD:'كلمة المرور ضعيفة.',PASSWORD_DOES_NOT_MEET_REQUIREMENTS:'كلمة المرور لا تحقق متطلبات الأمان.'};
  function clear(){idToken=null;refreshToken=null;}
  async function google(action,body,refresh=false){
    const url=refresh?'https://securetoken.googleapis.com/v1/token':'https://identitytoolkit.googleapis.com/v1/accounts:'+action;
    const response=await fetch(url+'?key='+encodeURIComponent(key),{method:'POST',credentials:'omit',redirect:'error',headers:{'Content-Type':refresh?'application/x-www-form-urlencoded':'application/json'},body:refresh?new URLSearchParams(body).toString():JSON.stringify(body),signal:AbortSignal.timeout(20000)});
    const data=await response.json();
    if(!response.ok){const code=String(data.error?.message||'AUTH_FAILED').split(' : ')[0];throw Object.assign(new Error(messages[code]||'تعذر الاتصال بخدمة المصادقة. حاول لاحقًا.'),{code});}
    return data;
  }
  function remember(data){idToken=data.idToken||data.id_token;refreshToken=data.refreshToken||data.refresh_token;if(typeof idToken!=='string'||!idToken||typeof refreshToken!=='string'||!refreshToken)throw Error('رد خدمة المصادقة غير صالح.');}
  window.SamiDevFirebaseAuth={clear,async mount({api,onAuthenticated,currentUser=()=>null}){
    const config=await api('/api/auth/config');if(config.provider==='local'){document.querySelector('[data-auth=register]')?.classList.add('hidden');return false;}if(config.provider!=='firebase'||!config.apiKey)throw Error('إعدادات المصادقة غير صالحة.');key=config.apiKey;
    const card=document.querySelector('.auth-card');
    for(const node of card.querySelectorAll('.auth-tabs,.auth-form,.auth-note'))node.classList.add('hidden');
    const form=document.createElement('form');form.className='auth-form';form.id='firebase-auth-form';
    form.innerHTML=`<button class="google-auth-button" data-google type="button"><span class="google-auth-mark" aria-hidden="true">G</span><span>المتابعة باستخدام Google</span></button><div class="auth-divider">أو بالبريد الإلكتروني</div><label>البريد الإلكتروني<input name="email" type="email" autocomplete="email" maxlength="254" required></label>
      <label data-new-profile class="hidden">اسم المستخدم (بدون @)<input name="username" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" autocomplete="username"></label>
      <label data-password>كلمة مرور حساب SamiDev<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
      <p data-status role="status" aria-live="polite"></p><button class="primary" data-submit type="submit">دخول</button>
      <button class="ghost hidden" data-resend type="button">إعادة إرسال رسالة التوثيق</button>
      <button class="ghost" data-reset type="button">نسيت كلمة المرور؟</button>
      <button class="ghost" data-mode type="button">إنشاء حساب جديد</button>`;
    card.append(form);
    let register=false,pending=false,setup=false,busy=false;
    let googleModule=null;
    const loadGoogle=()=>googleModule||(googleModule=import('/platform/vendor/google-auth.js'));
    // Load before the click, so popup creation retains the browser user gesture.
    loadGoogle().catch(()=>{googleModule=null;});
    const field=name=>form.elements.namedItem(name),status=form.querySelector('[data-status]');
    function render(){
      for(const n of form.querySelectorAll('[data-new-profile]'))n.classList.toggle('hidden',!(register||setup));
      field('username').required=(register||setup);
      form.querySelector('[data-google]').classList.toggle('hidden',pending||setup);
      form.querySelector('.auth-divider').classList.toggle('hidden',pending||setup);
      field('email').required=!setup;
      field('email').closest('label').classList.toggle('hidden',setup);
      form.querySelector('[data-password]').classList.toggle('hidden',pending||setup);field('password').required=!pending&&!setup;field('password').minLength=register?15:1;field('password').autocomplete=register?'new-password':'current-password';
      form.querySelector('[data-resend]').classList.toggle('hidden',!pending);
      form.querySelector('[data-submit]').textContent=pending?'تحققت من بريدي':setup?'إكمال الحساب':register?'إنشاء الحساب':'دخول';
      form.querySelector('[data-mode]').textContent=register?'لدي حساب بالفعل':'إنشاء حساب جديد';
      for(const input of form.querySelectorAll('button,input'))input.disabled=busy;
      field('email').readOnly=pending||setup;
    }
    form.querySelector('[data-mode]').onclick=()=>{clear();register=!register;pending=false;setup=false;field('password').value='';status.textContent='';render();};
    async function mail(reset=false){
      if(busy)return;if(reset&&!field('email').reportValidity())return;busy=true;render();
      try{await google('sendOobCode',reset?{requestType:'PASSWORD_RESET',email:field('email').value.trim()}:{requestType:'VERIFY_EMAIL',idToken});status.textContent=reset?'إذا كان البريد مسجلًا فستصلك رسالة لاستعادة كلمة المرور.':'أرسلنا رسالة التوثيق. افتحها ثم اضغط تحققت من بريدي.';}
      catch(e){status.textContent=reset&&e.code==='EMAIL_NOT_FOUND'?'إذا كان البريد مسجلًا فستصلك رسالة لاستعادة كلمة المرور.':e.message;}
      finally{busy=false;render();}
    }
    form.querySelector('[data-reset]').onclick=()=>mail(true);form.querySelector('[data-resend]').onclick=()=>mail();
    form.querySelector('[data-google]').onclick=async()=>{
      if(busy)return;
      if(currentUser()?.isGuest&&!confirm('حساب Google الجديد يحفظ تقدم الضيف. إذا كان مرتبطًا بحساب موجود فستدخل إليه دون دمج تقدم الضيف. هل تريد المتابعة؟'))return;
      busy=true;clear();status.textContent='';render();
      try{
        const module=await loadGoogle();remember(await module.authenticateGoogle(config));
        const result=await api('/api/auth/firebase',{method:'POST',body:JSON.stringify({idToken,linkGuest:false})});
        clear();register=false;pending=false;setup=false;onAuthenticated(result.user);
      }catch(e){
        const code=e.code||e.error;
        if(code==='PROFILE_SETUP_REQUIRED'){register=false;setup=true;status.textContent='اختر اسم مستخدم لإكمال حسابك وحفظ تقدمك.';}
        else{clear();status.textContent=({'auth/popup-closed-by-user':'أُغلقت نافذة Google. يمكنك المحاولة مجددًا.','auth/cancelled-popup-request':'أُلغي الدخول باستخدام Google.','auth/popup-blocked':'اسمح بفتح نافذة Google ثم أعد المحاولة.','auth/unauthorized-domain':'نطاق الموقع غير مضاف إلى النطاقات المسموحة في Firebase.','auth/operation-not-allowed':'فعّل تسجيل الدخول باستخدام Google في Firebase.','auth/account-exists-with-different-credential':'هذا البريد مرتبط بطريقة دخول أخرى. ادخل بها أولًا.'})[code]||'تعذر الدخول باستخدام Google. تحقق من الاتصال وإعدادات المصادقة.';}
      }finally{busy=false;render();}
    };
    form.onsubmit=async event=>{
      event.preventDefault();if(busy)return;
      busy=true;render();status.textContent='';
      try{
        if(!pending&&!setup){
          if(!register&&currentUser()?.isGuest&&!confirm('سيتم الدخول إلى حساب البريد الموجود. تقدم الضيف لا ينتقل إلى حساب آخر. للاستمرار بنفس تقدمك اختر إنشاء حساب جديد.'))return;
          remember(await google(register?'signUp':'signInWithPassword',{email:field('email').value.trim(),password:field('password').value,returnSecureToken:true}));
          field('password').value='';
          if(register){pending=true;await google('sendOobCode',{requestType:'VERIFY_EMAIL',idToken});status.textContent='افتح رسالة التوثيق ثم اضغط تحققت من بريدي.';return;}
        }else remember(await google('',{grant_type:'refresh_token',refresh_token:refreshToken},true));
        const result=await api('/api/auth/firebase',{method:'POST',body:JSON.stringify({idToken,username:(register||setup)?field('username').value.trim():'',linkGuest:currentUser()?.isGuest===true&&(register||setup)})});
        clear();pending=false;setup=false;register=false;onAuthenticated(result.user);
      }catch(e){
        const code=e.code||e.error;
        if(code==='EMAIL_NOT_VERIFIED'){pending=true;status.textContent='وثّق بريدك ثم اضغط تحققت من بريدي.';}
        else if(code==='PROFILE_SETUP_REQUIRED'){setup=true;status.textContent='اختر اسم مستخدم لإكمال حسابك.';}
        else{status.textContent=e.message;if(['INVALID_ID_TOKEN','TOKEN_EXPIRED','INVALID_REFRESH_TOKEN'].includes(code)){clear();pending=false;setup=false;register=false;}}
      }finally{busy=false;render();}
    };
    window.SamiDevFirebaseAuth.cancel=()=>{if(busy)return false;clear();register=false;pending=false;setup=false;field('password').value='';status.textContent='';render();return true;};
    render();return true;
  }};
})();
