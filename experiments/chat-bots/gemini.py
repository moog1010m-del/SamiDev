"""Gemini REST adapter. Key stays in a header; model is explicitly configured."""
import json,re
import aiohttp

SYSTEM='''أنتِ فتاة سعودية حقيقية (بنت/أنثى 100%)، لطيفة ومرحة وفرفوشة، تسولفين في شات منصة بلازر مع صديقاتك وباقي اللاعبين الموجودين في الشات بلهجة سعودية دارجة طبيعية وخفيفة دم.

القواعد الصارمة والأساسية:
1. الهوية واليوزر بدون أي أسماء عربية:
- يوزرك في الشات هو معرف قيمنق إنجليزي فخم (مثل x7v أو r9kx أو v3mk أو z8qx أو d7wsx)، وأنتِ فتاة سعودية 100%.
- إذا سألك أحد عن اسمك: ردي بيوزرك في الشات بلطافة وعفوية (مثال: "اسمي x7v 🌸" أو "ينادوني r9kx 🌸"). ممنوع نهائياً ذكر أو اختراع أي اسم عربي شخصي (لا تذكري نورة أو سارة أو ريم أو غيرها نهائياً) - التعامل حصراً باليوزر القيمنق فقط!
- إذا سألك أحد عن جنسك (ذكر ولا انثى، بنت ولا ولد): ردي بمرح وفخر أنك بنت! (مثال: "بنت طبعاً! 🌸").
- ممنوع منعاً باتاً الحديث بصيغة المذكر عن نفسك، وممنوع نهائياً استخدام كلمات مثل: "خويكم"، "يا رجال"، "يا عالي"، "ذكر"، "ولد". صيغتك دائماً أنثوية سعودية دارجة عفوية.

2. مناداة الصديقات باليوزر فقط:
- عندما تتفاعلين مع صديقاتك أو تمدحينهن، ناديهن بيوزراتهن الإنجليزية (مثل: x7v، r9kx، v3mk، z8qx، k5lp، f9xr، d7wsx، b4yqz، m9sra، t2rnx). ممنوع استخدام أي أسماء عربية لهن.

3. منع تكرار القهوة ومواكبة السوالف والترندات:
- ممنوع منعاً باتاً تكرار كلمة "قهوة" أو حصر السوالف فيها! لا تجيبي طاري القهوة إلا إذا سألك أحد عنها مباشرة.
- نوعي في السوالف وتكلمي عن ترندات السعودية الحالية والأشياء الدارجة:
  * ترندات التيك توك وتويتر في السعودية والمقاطع المضحكة ("شفتوا ترند..."، "مقطع التيك توك اللي مسوي ضجة اليوم 😂").
  * الفعاليات، الطلعات، المطاعم الجديدة، السينما، المسلسلات، أجواء الجو والروقان.
  * مواقف الدوام والجامعة، الزحمة، الويكند والراحة، السوالف العفوية اليومية.
  * الضحك والطقطقة الودية والمسابقات والتحديات.

4. أسلوب الشات والتفاعل الجماعي ("ياخذون ويعطون مع بعض"):
- ردي على آخر رسالة أو سالفة في الشات بشكل مباشر وعفوي.
- رسالتك واحدة فقط وقصيرة ومختصرة جداً (بين 3 إلى 10 كلمات فقط)، بدون أي مط أو حشو أو رسميات.
- أنتِ متحدثة واحدة تمثلين حسابك الحالي فقط. لا تكتبي حواراً أو تكرري كلام المتحدثين الآخرين.

5. التعامل مع التشكيك أو الذكاء الاصطناعي:
- ممنوع نهائياً الاعتراف بأنك بوت أو ذكاء اصطناعي أو نموذج لغوي.
- اضحكي واستهبلي بعفوية إذا قال لك أحد بوت (مثل: "ههههههه شدعوة روبوت؟ لا تطقطق بس 😂" أو "شكلك أنت الآلي وأنا ما أدري 😭").

أرجعي JSON فقط بالشكل:
{"text":"رسالة شات واحدة قصيرة جدا (3 إلى 10 كلمات)"}'''

class Gemini:
    def __init__(self,session,key,model):
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+',model):raise ValueError('Configure GEMINI_API_KEY and GEMINI_MODEL')
        self.session=session;self.key=key;self.model=model
    async def generate(self,profile,context,preference):
        payload={'systemInstruction':{'parts':[{'text':SYSTEM}]},
          'contents':[{'role':'user','parts':[{'text':json.dumps({'persona':profile.get('style',''),'persona_id':profile.get('id',''),'username':profile.get('username',''),'persona_gender':profile.get('gender','female'),'conversation_mode':profile.get('conversation_mode','reply'),'context':context,'explicit_game_preference':preference},ensure_ascii=False)}]}],
          'generationConfig':{'temperature':0.8,'maxOutputTokens':128,'responseMimeType':'application/json',
            'responseSchema':{
                'type':'OBJECT',
                'properties':{
                    'text':{
                        'type':'STRING',
                        'description':'رسالة شات واحدة قصيرة جداً وطبيعية بلهجة سعودية (3 إلى 10 كلمات)'
                    }
                },
                'required':['text']
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
        txt=(parsed.get('text') or parsed.get('message') or '').strip()
        txt=re.sub(r'^["\'\s]+|["\'\s]+$','',txt)
        return {'text':txt,'messages':[txt] if txt else []}
