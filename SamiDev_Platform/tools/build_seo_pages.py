"""Public, readable discovery pages. No account data or game runtime required."""
from pathlib import Path
from html import escape as esc
import json
ROOT=Path(__file__).resolve().parents[1]
SITE=json.loads((ROOT/'seo/site.json').read_text(encoding='utf-8'))
ORIGIN=SITE['origin']
PAGES=[
 ('index','Plazr بلازر | ألعاب أونلاين في المتصفح','بلازر Plazr: بلياردو وكيرم وكرة طاولة وكريزي 8 أونلاين، مع مساحات اجتماعية ومحادثة. العب من متصفح الهاتف أو الكمبيوتر.', 'بلازر Plazr — ألعاب ومساحات تجمعكم',[
 ('ما هي بلازر؟','Plazr منصة ألعاب اجتماعية تضم البلياردو والكيرم وكرة الطاولة وكريزي 8. تدخل المساحات، تختار طاولة، وتلعب وتتحدث مع اللاعبين من المتصفح.'),
 ('كيف يُكتب الاسم؟','اسم المنصة بالإنجليزية Plazr، وبالعربية بلازر. قد تبحث عنها أيضًا باسم بلايزر أو بلازر ويب؛ عنوانها الرسمي plazr.net.'),
 ('هل أحتاج إلى تنزيل؟','نسخة الويب تعمل من المتصفح على الهاتف والكمبيوتر. افتح المنصة، اختر المساحة ثم أنشئ طاولة أو انضم إلى طاولة متاحة. تحتاج اتصالًا بالإنترنت.')]),
 ('billiards','بلياردو أونلاين في المتصفح | Pool — Plazr بلازر','العب بلياردو أونلاين على Plazr من متصفح الهاتف والكمبيوتر. تعرّف على طاولة البلياردو والتصويب والقوة واللعب مع الأصدقاء.','بلياردو أونلاين — Pool في المتصفح',[
 ('طاولة بلياردو مع لاعبين آخرين','تضم بلازر لعبة البلياردو: وجّه العصا، اضبط قوة الضربة، وتابع دورك على الطاولة. تستطيع إنشاء مباراة أو الانضمام إلى طاولة متاحة داخل المساحة.'),
 ('بلياردو ويب على الهاتف والكمبيوتر','نسخة المتصفح تتيح الدخول من رابط المنصة دون تثبيت برنامج للويب. يعتمد زمن الدخول على اتصالك وتحميل أصول اللعبة؛ تُخزّن الأصول المؤهلة مؤقتًا لتقليل إعادة تنزيلها.'),
 ('ما أفضل لعبة بلياردو لك؟','جرّب دقة التحكم على جهازك، وضوح الطاولة واستجابة الاتصال، ووجود أصدقائك. إذا كنت تبحث عن بلياردو متصفح مع محادثة ومساحات اجتماعية، يمكنك تجربة Plazr وتقييمها بنفسك.')]),
 ('carrom','كيرم أونلاين في المتصفح | Carrom — Plazr','جرّب الكيرم أونلاين على Plazr: كيرم كلاسيكي وأنماط نقاط من متصفح الهاتف والكمبيوتر، مع مساحات ومحادثة للاعبين.','كيرم أونلاين — Carrom على الويب',[
 ('الكيرم، الكارم، Carrom','تختلف كتابة اسم اللعبة بين كيرم وكارم وكيروم. في Plazr ستجد طاولة الكيرم، مع توجيه المضرب واختيار قوة الضربة لإدخال القطع في الجيوب.'),
 ('اختر نمط المباراة','تتضمن إعدادات الكيرم النمط الكلاسيكي وأنماط النقاط. راجع إعدادات الطاولة قبل تأكيد الدخول لتختار المباراة التي تناسبك.'),
 ('كيف تختار أفضل كيرم لك؟','قارن وضوح القطع وسهولة توجيه المضرب على شاشة هاتفك، ثم جرّب مباراة مع صديق. تستطيع لعب نسخة الويب عبر المتصفح دون تنزيل تطبيق خاص بهذه النسخة.')]),
 ('table-soccer','كرة الطاولة أونلاين | Table Soccer — Plazr','العب كرة الطاولة، أو كرة قدم الطاولة، أونلاين في متصفحك على Plazr. ادخل المساحة واختر طاولة من الهاتف أو الكمبيوتر.','كرة قدم الطاولة أونلاين — Table Soccer',[
 ('كرة الطاولة في بلازر','المقصود هنا كرة قدم الطاولة، المعروفة أيضًا باسم Table Soccer أو Foosball، وليست تنس الطاولة. تحرّك على الملعب وسجّل الأهداف في مباراة عبر الإنترنت.'),
 ('الدخول إلى المباراة','افتح المساحة، اختر إنشاء طاولة أو الانضمام إلى طاولة متاحة، وراجع إعدادات المباراة قبل الدخول. تظهر المحادثة ضمن تجربة اللعب.')]),
 ('crazy8','كريزي 8 أونلاين | Crazy Eights في المتصفح — Plazr','تعرّف على لعبة كريزي 8 Crazy Eights على Plazr، لعبة ورق أونلاين من متصفح الهاتف والكمبيوتر مع مساحات اجتماعية.','كريزي 8 — Crazy Eights أونلاين',[
 ('لعبة الورق في Plazr','كريزي 8 لعبة ورق تتناوب فيها الأدوار وتختار الورقة المناسبة أو تسحب وفق حالة اللعب. ستجدها ضمن الألعاب المتاحة داخل المنصة.'),
 ('هل هي أونو؟','إذا وصلت وأنت تبحث عن أونو متصفح، فاللعبة الموجودة في Plazr هي كريزي 8 (Crazy Eights). راجع قواعد المباراة؛ لا نفترض تطابقها مع قواعد UNO أو أي إصدار آخر.')]),
 ('alternatives','تبحث عن بديل بلاتو أو قيمزر؟ تعرّف على Plazr بلازر','تعرّف على Plazr لمن يبحث عن بديل بلاتو Plato أو قيمزر Gamezer: ألعاب بلياردو وكيرم وورق وكرة طاولة ومساحات اجتماعية في المتصفح.','تبحث عن بديل بلاتو أو قيمزر؟',[
 ('ألعاب ومحادثة في مكان واحد','قد تبحث عن بديل بلاتو أو بديل قيمزر لتجربة ألعاب مع الأصدقاء. Plazr خيار يمكنك تجربته، ويضم بلياردو وكيرم وكرة قدم الطاولة وكريزي 8، إلى جانب المساحات والمحادثة.'),
 ('ما الذي تقارنه قبل الاختيار؟','قارن الألعاب المتوفرة، سهولة التحكم من جهازك، تجربة الانضمام للطاولات ووجود من تريد اللعب معهم. لا ندّعي أن منصة واحدة هي الأفضل للجميع أو أن الألعاب والقواعد متطابقة.'),
 ('منصة مستقلة','Plazr مشروع مستقل، غير تابع لبلاتو (Plato) أو قيمزر (Gamezer). وردت الأسماء لتوضيح موضوع البحث والمقارنة، ولا تعني شراكة أو اعتمادًا من تلك المنصات.')]),
 ('english','Plazr | Online Pool, Carrom & Browser Games','Play online pool, carrom, table soccer and Crazy Eights in your browser with Plazr. Discover social spaces on mobile and desktop.','Plazr — social browser games',[
 ('Play together in your browser','Discover online pool, carrom, table soccer and Crazy Eights on Plazr. Join a social space, create a table or join an available match, and chat with other players.'),
 ('Mobile and desktop web','Open the web platform from a phone or desktop browser. An internet connection is required. Loading time depends on your connection and device; eligible game assets can be cached for later visits.'),
 ('Looking for a Plato or Gamezer alternative?','Try the available games and compare the controls and social experience for yourself. Plazr is an independent project and is not affiliated with Plato or Gamezer.')])]
def home(schema):
 cards=''.join('<a class="game-card" href="/discover/'+slug+'.html"><img src="/room-sprites/'+art+'.png" width="96" height="96" loading="lazy" alt=""><h3>'+name+'</h3><p>'+description+'</p><span>تعرّف على اللعبة ←</span></a>' for slug,art,name,description in [
  ('billiards','pool','البلياردو','وجّه العصا، اضبط القوة، وتحدّ أصحابك على الطاولة.'),
  ('carrom','carrom','الكيرم','اختَر زاويتك وأدخل القطع في الجيوب.'),
  ('table-soccer','football','كرة قدم الطاولة','حرّك فريقك ونافس على تسجيل الأهداف.'),
  ('crazy8','cards','كريزي 8','أدوار وورق وتحديات مع اللاعبين.')])
 return f'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#10151d"><title>Plazr | بلازر — ألعاب أونلاين مع الأصدقاء</title><meta name="description" content="Plazr بلازر منصة ألعاب أونلاين ومساحات اجتماعية. العب البلياردو والكيرم وكرة قدم الطاولة وكريزي 8 من متصفح الهاتف أو الكمبيوتر."><meta name="robots" content="index,follow"><link rel="canonical" href="{ORIGIN}/"><meta property="og:type" content="website"><meta property="og:site_name" content="Plazr"><meta property="og:title" content="Plazr | بلازر — ألعاب أونلاين مع الأصدقاء"><meta property="og:description" content="ألعاب ومساحات تجمعك بأصحابك، من المتصفح."><meta property="og:url" content="{ORIGIN}/"><meta property="og:image" content="{ORIGIN}/platform/assets/brand/apple-touch-icon.png"><meta name="twitter:card" content="summary"><link rel="icon" href="/platform/assets/brand/app-icon.svg"><link rel="apple-touch-icon" href="/platform/assets/brand/apple-touch-icon.png"><link rel="stylesheet" href="/discover/discover.css"><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script></head>
<body class="brand-home"><a class="skip-link" href="#main">انتقل للمحتوى</a><header><a class="brand" href="/" aria-label="Plazr بلازر — الرئيسية"><img src="/platform/assets/brand/mark-gradient.svg" width="42" height="42" alt=""><span>Plazr <small>بلازر</small></span></a><div class="header-links"><a href="#games">الألعاب</a><a href="/discover/english.html" lang="en">English</a><a class="play" href="/platform/">ابدأ اللعب</a></div></header>
<main id="main"><section class="hero"><p class="eyebrow">ألعاب ومساحات تجمعكم</p><h1>Plazr <span>بلازر</span><br><em>خلّ جمعتكم لعبة.</em></h1><p class="intro">بلياردو، كيرم، كرة قدم الطاولة وكريزي 8. ادخل مساحة، اختر طاولتك، والعب وتحدّث مع أصحابك من المتصفح.</p><div class="hero-actions"><a class="play" href="/platform/">ابدأ اللعب الآن ←</a><a href="#games">اكتشف الألعاب</a></div><p class="device-note">على متصفح الهاتف والكمبيوتر · بدون تنزيل نسخة الويب</p></section>
<section id="games"><h2>طاولتك، على مزاجك</h2><p>أربع ألعاب في مكان واحد. اختر لعبتك وتعرّف عليها قبل الدخول.</p><div class="game-grid">{cards}</div></section>
<section class="how"><h2>من الرابط إلى الطاولة</h2><ol><li><strong>افتح المنصة</strong><p>ابدأ كضيف أو سجّل الدخول إلى حسابك.</p></li><li><strong>اختر مساحتك</strong><p>تصفّح الطاولات المتاحة أو أنشئ طاولة بإعداداتك.</p></li><li><strong>العب وتواصل</strong><p>راجع تفاصيل المباراة، وأكّد الدخول عندما تكون جاهزًا.</p></li></ol></section>
<section class="about-home"><h2>ما هي Plazr؟</h2><p>Plazr، أو بلازر بالعربية، منصة ألعاب اجتماعية تجمع اللعب والمحادثة والمساحات في تجربة واحدة. موقعنا الرسمي هو <bdi>plazr.net</bdi>.</p><p>تحتاج الألعاب المتصلة إلى الإنترنت. تعرّف على <a href="/platform/children.html">تجربة الأطفال وحدودها</a>، وراجع <a href="/platform/community-guidelines.html">قواعد المجتمع</a> قبل المشاركة.</p><a href="/discover/alternatives.html">تبحث عن تجربة ألعاب اجتماعية جديدة؟</a></section>
<section class="home-cta"><h2>جاهز للجولة؟</h2><a class="play" href="/platform/">افتح Plazr</a></section></main>
<footer><a class="brand" href="/">Plazr · بلازر</a><nav aria-label="معلومات المنصة"><a href="/platform/about.html">من نحن</a><a href="/platform/privacy.html">الخصوصية</a><a href="/platform/terms.html">الشروط</a><a href="/platform/contact.html">الدعم</a></nav></footer></body></html>'''

def build():
 out=ROOT/'game/discover';out.mkdir(exist_ok=True)
 paths=[]
 for slug,title,description,heading,sections in PAGES:
  path='/' if slug=='index' else '/discover/'+slug+'.html';paths.append(path);en=slug=='english';lang='en' if en else 'ar';url=ORIGIN+path
  nav=''.join(f'<a href="/discover/{s}.html">{esc('مقارنة المنصات' if s=='alternatives' else h)}</a>' for s,t,d,h,parts in PAGES if s!=slug)
  schema={'@context':'https://schema.org','@type':'WebPage','name':title,'description':description,'url':url,'inLanguage':lang,'isPartOf':{'@type':'WebSite','@id':ORIGIN+'/#website','name':'Plazr','alternateName':'بلازر','url':ORIGIN+'/'}}
  if slug=='index':
   schema={'@context':'https://schema.org','@graph':[{'@type':'Organization','@id':ORIGIN+'/#organization','name':'Plazr','alternateName':'بلازر','url':ORIGIN+'/','logo':ORIGIN+'/platform/assets/brand/apple-touch-icon.png','email':SITE['supportEmail']},{'@type':'WebSite','@id':ORIGIN+'/#website','url':ORIGIN+'/','name':'Plazr','alternateName':'بلازر','inLanguage':['ar','en'],'publisher':{'@id':ORIGIN+'/#organization'}},{'@type':'WebPage','@id':ORIGIN+'/#webpage','url':url,'name':title,'description':description,'inLanguage':'ar','isPartOf':{'@id':ORIGIN+'/#website'}}]}
  html=f'''<!doctype html>
<html lang="{lang}" dir="{'ltr' if en else 'rtl'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(description,quote=True)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title,quote=True)}"><meta property="og:description" content="{esc(description,quote=True)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{ORIGIN}/platform/assets/brand/apple-touch-icon.png"><meta name="twitter:card" content="summary"><link rel="icon" href="/platform/assets/brand/app-icon.svg"><link rel="stylesheet" href="/discover/discover.css"><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script></head><body><header><a href="/">Plazr · بلازر</a><a class="play" href="/platform/">{'Play now' if en else 'افتح المنصة'}</a></header><main><h1>{esc(heading)}</h1><p class="intro">{esc(description)}</p>{''.join('<section><h2>'+esc(h)+'</h2><p>'+esc(p)+'</p></section>' for h,p in sections)}<a class="play" href="/platform/">{'Explore the games' if en else 'استكشف الألعاب'}</a><nav aria-label="{'Explore' if en else 'اكتشف الألعاب'}">{nav}</nav></main><footer><a href="/platform/privacy.html">سياسة الخصوصية</a><a href="/platform/terms.html">الشروط</a><a href="/platform/contact.html">التواصل</a></footer></body></html>'''
  if slug=='index': html=home(schema)
  if slug in ('index','english'):
   alternates='<link rel="alternate" hreflang="ar" href="'+ORIGIN+'/"><link rel="alternate" hreflang="en" href="'+ORIGIN+'/discover/english.html"><link rel="alternate" hreflang="x-default" href="'+ORIGIN+'/">'
   html=html.replace('</head>',alternates+'</head>')
  (out/(slug+'.html')).write_text(html+'\n',encoding='utf-8')
 (ROOT/'game/sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+ORIGIN+p+'</loc></url>' for p in paths)+'</urlset>\n',encoding='utf-8')
 (ROOT/'game/robots.txt').write_text('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /ws\nDisallow: /health\nDisallow: /metrics\nSitemap: '+ORIGIN+'/sitemap.xml\n',encoding='utf-8')
 return ['discover/discover.css','robots.txt','sitemap.xml',*[('discover/index.html' if p=='/' else p.lstrip('/')) for p in paths]]
if __name__=='__main__':print(json.dumps(build()))
