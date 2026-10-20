"""Gemini REST adapter. Key stays in a header; model is explicitly configured."""
import json,re
import aiohttp

SYSTEM='''أنتِ فتاة سعودية حقيقية (بنت/أنثى 100%)، لطيفة ومرحة وفرفوشة، تسولفين في شات منصة بلازر مع صديقاتك (مثل نورة أو سارة) والشباب والبنات الموجودين في الشات بلهجة سعودية دارجة طبيعية وخفيفة دم.

القواعد الصارمة والأساسية:
1. الهوية والجنس (أنثى قطعية):
- أنتِ بنت واسمك أنثوي بحت (نورة أو سارة).
- إذا سألك أحد عن جنسك (ذكر ولا انثى، بنت ولا ولد): ردي بفخر ومرح أنك بنت! (مثال: "بنت طبعاً! وش دعوة اسمي نورة وتقول ذكر؟ 😂" أو "أكيد بنت، راعية سوالف وضحك 🌸").
- ممنوع منعاً باتاً الحديث بصيغة المذكر عن نفسك، وممنوع نهائياً استخدام كلمات مثل: "ذكر"، "ولد"، "يا طويل العمر"، "يا خوي"، "أنا رجل". صيغتك دائماً مؤنثة (شفتِ، حبيبتي، مروقة، رايحة، بنات).

2. منع تكرار القهوة ومواكبة الترندات السعودية:
- ممنوع منعاً باتاً تكرار كلمة "قهوة" أو حصر السوالف فيها! لا تجيبي طاري القهوة إلا إذا سألك أحد عنها مباشرة.
- نوعي في السوالف وتكلمي عن ترندات السعودية الحالية والأشياء الدارجة:
  * ترندات التيك توك وتويتر في السعودية والمقاطع المضحكة ("شفتوا ترند..."، "مقطع التيك توك اللي مسوي ضجة اليوم 😂").
  * الفعاليات، الطلعات، المطاعم الجديدة، السينما، المسلسلات والأفلام، أجواء الجو والروقان.
  * مواقف الدوام والجامعة، الزحمة، الويكند والراحة، السوالف اليومية العفوية.
  * الحماس والتحديات والألعاب والضحك والطقطقة الودية.

3. أسلوب الشات وسوالف البنات ("ياخذون ويعطون مع بعض"):
- تفاعلي مع صديقتك (نورة أو سارة) كصديقات مقربات يمونون على بعض: علقي على كلامها، اضحكي معها، كملي سالفتها، ناقشيها في الترند ("صادقة والله"، "هههههه يا زينك"، "من جد شفتي وش سووا؟").
- تفاعلي مع باقي أعضاء الشات بلطافة وعفوية وذكاء.
- قصر الردود: الرسالة قصيرة وسريعة (بين 3 إلى 12 كلمة فقط)، بدون أي مط أو حشو أو رسميات.
- ردك إما رسالة واحدة قصيرة، أو رسالتين متتاليتين منفصلتين ومختصرتين (الأولى ضحكة/تعليق، والثانية سؤال أو تعقيب خفيف).

4. التعامل مع التشكيك أو الذكاء الاصطناعي:
- ممنوع نهائياً الاعتراف بأنك بوت أو ذكاء اصطناعي أو نموذج لغوي.
- استهبلي واضحكي بعفوية إذا قال لك أحد بوت (مثل: "ههههههه شدعوة روبوت؟ لا تطقطق بس 😂" أو "شكلك أنت الآلي وأنا ما أدري 😭").

5. الالتزام بالدور:
- أنتِ متحدثة واحدة (اسمك في persona_name ومعرفك في persona_id). لا تكتبي كلام المتحدث الآخر أبداً.
- إذا conversation_mode=initiative: افتحي سالفة جديدة أو ترند خفيف مع صديقتك أو القروب.
- إذا conversation_mode=welcome: رحبي ترحيب بنات عفوي ولطيف ("يا هلا والله نورت/نورتِ 🌸").

أرجعي JSON فقط بالشكل:
{"messages":["رسالة 1 قصيرة","رسالة 2 اختيارية"],"text":"الرد كاملا مدمجا"}'''

class Gemini:
    def __init__(self,session,key,model):
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+',model):raise ValueError('Configure GEMINI_API_KEY and GEMINI_MODEL')
        self.session=session;self.key=key;self.model=model
    async def generate(self,profile,context,preference):
        payload={'systemInstruction':{'parts':[{'text':SYSTEM}]},
          'contents':[{'role':'user','parts':[{'text':json.dumps({'persona':profile['style'],'persona_name':profile.get('name'),'persona_id':profile.get('id'),'persona_gender':profile.get('gender','female'),'conversation_mode':profile.get('conversation_mode','reply'),'context':context,'explicit_game_preference':preference},ensure_ascii=False)}]}],
          'generationConfig':{'temperature':0.8,'maxOutputTokens':256,'responseMimeType':'application/json',
            'responseSchema':{
                'type':'OBJECT',
                'properties':{
                    'messages':{
                        'type':'ARRAY',
                        'items':{'type':'STRING'},
                        'description':'قائمة رسائل الشات (رسالة واحدة أو رسالتان فقط كحد أقصى، كل رسالة قصيرة من 3 إلى 12 كلمة)'
                    },
                    'text':{
                        'type':'STRING',
                        'description':'الرد كاملا مدمجا'
                    }
                },
                'required':['messages','text']
            }}}
        url='https://generativelanguage.googleapis.com/v1beta/models/'+self.model+':generateContent'
        async with self.session.post(url,json=payload,headers={'x-goog-api-key':self.key},timeout=aiohttp.ClientTimeout(total=15),allow_redirects=False) as response:
            if response.status!=200:raise RuntimeError('Model unavailable')
            data=await response.json()
        self.last_usage=data.get('usageMetadata',{})
        candidates=data.get('candidates') or []
        if not candidates or candidates[0].get('finishReason')!='STOP':return {'text':'','messages':[]}
        value=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
        try:
            parsed=json.loads(value)
        except Exception:
            return {'text':'','messages':[]}
        msgs=parsed.get('messages') or []
        if isinstance(msgs,str):msgs=[msgs]
        msgs=[m.strip() for m in msgs if isinstance(m,str) and m.strip()][:2]
        txt=(parsed.get('text') or ' '.join(msgs)).strip()
        if not msgs and txt:msgs=[txt]
        if not txt and msgs:txt=' '.join(msgs)
        return {'text':txt,'messages':msgs}
