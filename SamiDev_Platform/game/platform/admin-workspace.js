(()=>{
 'use strict';
 const root=document.querySelector('#page-admin');if(!root)return;
 const tabs=[...root.querySelectorAll('[data-admin-tab]')],form=root.querySelector('#admin-community-editor');
 let communities=[],selected=null,loading=false;
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const status=(text,error=false)=>{const box=root.querySelector('#admin-community-status');box.textContent=text;box.dataset.error=String(error);};
 async function api(path='',body){const response=await fetch('/api/admin/communities'+path,{method:body?(path?'PATCH':'POST'):'GET',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok||!data.ok)throw Error(data.message||'تعذر تحميل المساحات');return data;}
 function edit(item){
  selected=item?.id||null;form.reset();
  for(const key of ['id','name','description','mark','countryCode','accent','order'])form.elements.namedItem(key).value=item?.[key]??({mark:'🌐',accent:'#27927b',order:communities.length+1}[key]??'');
  form.elements.namedItem('id').readOnly=!!selected;form.elements.namedItem('enabled').checked=item?.enabled!==false;
  root.querySelector('#admin-community-editor-title').textContent=selected?'تعديل المساحة':'مساحة جديدة';
 }
 function draw(){root.querySelector('#admin-community-list').innerHTML=communities.map(c=>`<article class="admin-community-card" data-community="${escape(c.id)}"><div><h4>${escape(c.mark)} ${escape(c.name)}</h4><small dir="ltr">${escape(c.id)}</small><span class="admin-community-state" data-enabled="${c.enabled!==false}">${c.enabled===false?'متوقفة مؤقتًا':'مفعلة'} · ${Number(c.onlineCount)||0} متصل</span></div><div class="admin-community-actions"><button class="ghost" type="button" data-edit="${escape(c.id)}">تعديل</button><button class="${c.enabled===false?'primary':'danger-btn'}" type="button" data-toggle="${escape(c.id)}">${c.enabled===false?'تفعيل':'تعطيل مؤقت'}</button></div></article>`).join('');
  root.querySelectorAll('[data-edit]').forEach(button=>button.onclick=()=>{edit(communities.find(c=>c.id===button.dataset.edit));form.scrollIntoView({block:'nearest',behavior:'smooth'});});
  root.querySelectorAll('[data-toggle]').forEach(button=>button.onclick=async()=>{const item=communities.find(c=>c.id===button.dataset.toggle);button.disabled=true;try{await api('/'+encodeURIComponent(item.id),{enabled:item.enabled===false});await load();status(item.enabled===false?'تم تفعيل المساحة':'تم تعطيل المساحة مؤقتًا مع حفظ بياناتها');}catch(error){status(error.message,true);button.disabled=false;}});
 }
 async function load(){if(loading)return;loading=true;try{const data=await api();communities=data.communities;draw();if(selected)edit(communities.find(c=>c.id===selected));}catch(error){status(error.message,true);}finally{loading=false;}}
 function activate(key){for(const tab of tabs){const active=tab.dataset.adminTab===key;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;root.querySelector('#'+tab.getAttribute('aria-controls')).hidden=!active;}if(key==='communities')load();}
 tabs.forEach((tab,index)=>{tab.onclick=()=>activate(tab.dataset.adminTab);tab.onkeydown=event=>{let next;if(event.key==='ArrowLeft')next=(index+1)%tabs.length;else if(event.key==='ArrowRight')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();tabs[next].focus();activate(tabs[next].dataset.adminTab);};});
 root.querySelector('#admin-community-new').onclick=()=>{edit(null);form.elements.namedItem('id').focus();};
 root.querySelector('#admin-refresh').addEventListener('click',()=>{if(root.querySelector('#admin-tab-communities').getAttribute('aria-selected')==='true')load();});
 form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;const body=Object.fromEntries(['name','description','mark','countryCode','accent'].map(key=>[key,form.elements.namedItem(key).value]));body.order=Number(form.elements.namedItem('order').value);body.enabled=form.elements.namedItem('enabled').checked;if(!selected)body.id=form.elements.namedItem('id').value;try{const data=await api(selected?'/'+encodeURIComponent(selected):'',body);selected=data.community.id;await load();status('تم حفظ المساحة');}catch(error){status(error.message,true);}finally{button.disabled=false;}};
 edit(null);
})();
