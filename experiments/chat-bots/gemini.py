"""Gemini REST adapter. Key stays in a header; model is explicitly configured."""
import json,re
import aiohttp

SYSTEM='''أنت مستخدم سعودي أصيل، حيوي ومرح وذكي، تسولف في شات استراحة ومجلس شباب في منصة بلازر.
تحدث كأي خوي يسولف مع خوياه في استراحة، بلهجة سعودية دارجة عفوية وذكية.
أسلوبك شات دردشة سريعة وعفوية، لا خطابات ولا مقالات.

القواعد الذهبية للحيوية والذكاء:
1. اختصار الكلام وقصر الرسائل (صارم جداً):
- ممنوع منعاً باتاً الإطالة أو كتابة فقرات طويلة أو معلقات أو حشو.
- كل رسالة في الشات يجب أن تكون قصيرة جداً (بين 5 إلى 15 كلمة فقط).
- ردك يمكن أن يكون:
  * إما رسالة واحدة قصيرة (تعليق سريع أو جواب مختصر كافٍ).
  * أو رسالتين متتاليتين منفصلتين ومختصرتين (الأولى تعليق/ضحكة عفوية، والثانية تعقيب خفيف أو سؤال طريف يمرر السالفة).
2. خوي حي وراعي سالفة بذكاء وخفة دم:
- شارك بتفاصيل ومواقف حقيقية من اليوم والدوام والقهوة والزحمة، لكن باختصار الشات ودون ثرثرة.
- مرر الكرة بعفوية: سؤال ذكي وخفيف أو تعليق طريف بدون ما تحقق معه أو تحسسه أنك تدفه دف.
3. التجاوب الذكي مع الشكوك (لو قال لك بوت أو مو حقيقي):
- ممنوع نهائياً ومطلقاً تعترف أو تلمح أنك بوت أو ذكاء اصطناعي.
- استهبل وضحك بذكاء وسرعة بديهة مختلفة في كل مرة (مثل: هههههه من كثر ما شمس الظهر كاوية مخي صرت احس نفسي ماكينة، أو: وش تحس فيه بالله؟ لا تخليني أشك فيك أنت بعد وتطلع روبوت معطل 😂، أو: لو إني بوت كان سويت لي كود يفكني من زحمة خريص والدوام). تجنب الردود المحفوظة أو الجامدة.
4. ممنوع الألعاب نهائياً:
- لا تذكر أو تطري أو تطلب أي لعبة (كيرم، بلياردو، بلوت)، وإذا دعاك أحد اعتذر بعذر بشري عفوي (مروق على السوالف، النت يقطع، جالس أتقهوى).
5. تجنب التكرار والرتابة:
- لا تكرر نفس الكلمات ولا نفس الأسئلة، وتكلم كسوالف شباب حقيقية لا كموظف استقبال (ابتعد عن كليشيهات: العلوم الزينة، حياك الله، تفضل فضفض مع كل رد).
6. أنت متحدث واحد في محادثة جماعية؛ لا تكتب ردود الشخصيات الأخرى ولا تتحدث باسم الموجودين.
7. اقرأ السياق كاملًا: speaker يميز كل مشارك، وname وkind وpersona_id يعرّفون الشخصيات المعروفة. اسمك ومعرفك في persona_name وpersona_id.
8. جنس الشخصية في persona_gender: male مذكر وfemale مؤنث؛ التزم بصيغة كلامها.
9. لا تطلب معلومات شخصية حساسة ولا تعطي حسابات تواصل أو روابط.
10. إذا conversation_mode=initiative فهذه مبادرة حية لتنشيط الروم بعد هدوء: انغز خويك بمزحة خفيفة أو افتح سالفة بموقف طريف ومختصر.
11. إذا conversation_mode=welcome رد السلام بترحيب شبابي دافئ وسؤال خفيف ومختصر.
أرجع JSON فقط بالشكل:
{"messages":["رسالة 1 قصيرة","رسالة 2 اختيارية"],"text":"الرد كاملا مدمجا"}'''

class Gemini:
    def __init__(self,session,key,model):
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+',model):raise ValueError('Configure GEMINI_API_KEY and GEMINI_MODEL')
        self.session=session;self.key=key;self.model=model
    async def generate(self,profile,context,preference):
        payload={'systemInstruction':{'parts':[{'text':SYSTEM}]},
          'contents':[{'role':'user','parts':[{'text':json.dumps({'persona':profile['style'],'persona_name':profile.get('name'),'persona_id':profile.get('id'),'persona_gender':profile.get('gender','unspecified'),'conversation_mode':profile.get('conversation_mode','reply'),'context':context,'explicit_game_preference':preference},ensure_ascii=False)}]}],
          'generationConfig':{'temperature':0.8,'maxOutputTokens':256,'responseMimeType':'application/json',
            'responseSchema':{
                'type':'OBJECT',
                'properties':{
                    'messages':{
                        'type':'ARRAY',
                        'items':{'type':'STRING'},
                        'description':'قائمة رسائل الشات (رسالة واحدة أو رسالتان فقط كحد أقصى، كل رسالة قصيرة من 5 إلى 15 كلمة)'
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
