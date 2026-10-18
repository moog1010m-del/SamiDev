"""Public, readable discovery pages. No account data or game runtime required."""
from pathlib import Path
from html import escape as esc
import json
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://plazr.cc'
PAGES=[
 ('index','Plazr بلازر | ألعاب أونلاين في المتصفح','بلازر Plazr: بلياردو وكيرم وكرة طاولة وكريزي 8 أونلاين، مع مساحات اجتماعية ومحادثة. العب من متصفح الهاتف أو الكمبيوتر.', 'بلازر Plazr — ألعاب ومساحات تجمعكم',[
 ('ما هي بلازر؟','Plazr منصة ألعاب اجتماعية تضم البلياردو والكيرم وكرة الطاولة وكريزي 8. تدخل المساحات، تختار طاولة، وتلعب وتتحدث مع اللاعبين من المتصفح.'),
 ('كيف يُكتب الاسم؟','اسم المنصة بالإنجليزية Plazr، وبالعربية بلازر. قد تبحث عنها أيضًا باسم بلايزر أو بلازر ويب؛ عنوانها الرسمي plazr.cc.'),
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
def build():
 out=ROOT/'game/discover';out.mkdir(exist_ok=True)
 paths=[]
 for slug,title,description,heading,sections in PAGES:
  path='/discover/'+slug+'.html';paths.append(path);en=slug=='english';lang='en' if en else 'ar';url=ORIGIN+path
  nav=''.join(f'<a href="/discover/{s}.html">{esc('مقارنة المنصات' if s=='alternatives' else h)}</a>' for s,t,d,h,parts in PAGES if s!=slug)
  schema={'@context':'https://schema.org','@type':'WebPage','name':title,'description':description,'url':url,'inLanguage':lang,'isPartOf':{'@type':'WebSite','name':'Plazr','alternateName':['بلازر','بلايزر'],'url':ORIGIN+'/platform/'}}
  html=f'''<!doctype html>
<html lang="{lang}" dir="{'ltr' if en else 'rtl'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(description,quote=True)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title,quote=True)}"><meta property="og:description" content="{esc(description,quote=True)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{ORIGIN}/platform/assets/brand/apple-touch-icon.png"><meta name="twitter:card" content="summary"><link rel="icon" href="/platform/assets/brand/app-icon.svg"><link rel="stylesheet" href="/discover/discover.css"><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script></head><body><header><a href="/discover/index.html">Plazr · بلازر</a><a class="play" href="/platform/">{'Play now' if en else 'افتح المنصة'}</a></header><main><h1>{esc(heading)}</h1><p class="intro">{esc(description)}</p>{''.join('<section><h2>'+esc(h)+'</h2><p>'+esc(p)+'</p></section>' for h,p in sections)}<a class="play" href="/platform/">{'Explore the games' if en else 'استكشف الألعاب'}</a><nav aria-label="{'Explore' if en else 'اكتشف الألعاب'}">{nav}</nav></main><footer><a href="/platform/privacy.html">سياسة الخصوصية</a><a href="/platform/terms.html">الشروط</a><a href="/platform/contact.html">التواصل</a></footer></body></html>'''
  (out/(slug+'.html')).write_text(html+'\n',encoding='utf-8')
 (ROOT/'game/sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+ORIGIN+p+'</loc></url>' for p in ['/platform/',*paths])+'</urlset>\n',encoding='utf-8')
 (ROOT/'game/robots.txt').write_text('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /ws\nDisallow: /health\nDisallow: /metrics\nSitemap: '+ORIGIN+'/sitemap.xml\n',encoding='utf-8')
 return ['discover/discover.css','robots.txt','sitemap.xml',*[p.lstrip('/') for p in paths]]
if __name__=='__main__':print(json.dumps(build()))
