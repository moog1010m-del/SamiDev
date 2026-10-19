import json,unittest
from gemini import Gemini
class Response:
    def __init__(self,status,data):self.status=status;self.data=data
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def json(self):return self.data
class Session:
    def __init__(self,status=200,finish='STOP'):
        self.status=status;self.finish=finish;self.request=None
    def post(self,url,**kwargs):
        self.request=(url,kwargs)
        return Response(self.status,{'candidates':[{'finishReason':self.finish,'content':{'parts':[{'text':'{"text":"هلا والله","messages":["هلا والله"]}'}]}}]})
class GeminiTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_request_and_key_not_in_url(self):
        session=Session();provider=Gemini(session,'test-only-secret','test-model')
        self.assertEqual(await provider.generate({'style':'سعودي'},[],'الكيرم'),{'text':'هلا والله','messages':['هلا والله']})
        url,request=session.request
        self.assertNotIn('test-only-secret',url);self.assertFalse(request['allow_redirects'])
        self.assertEqual(request['json']['generationConfig']['responseMimeType'],'application/json')
    async def test_group_context_and_selected_persona_reach_model(self):
        session=Session();provider=Gemini(session,'test','model')
        context=[{'speaker':'participant-1','name':'نواف','kind':'bot','persona_id':'nawaf','text':'هلا والله'},
                 {'speaker':'participant-2','text':'أي سوالف؟'}]
        await provider.generate({'id':'fahad','name':'فهد','style':'سعودي هادي'},context,None)
        payload=session.request[1]['json']
        content=json.loads(payload['contents'][0]['parts'][0]['text'])
        self.assertEqual(content['persona_id'],'fahad')
        self.assertEqual(content['persona_name'],'فهد')
        self.assertEqual(content['context'],context)
    async def test_gender_is_explicit_even_when_name_suggests_otherwise(self):
        session=Session();provider=Gemini(session,'test','model')
        await provider.generate({'id':'faisal','name':'فيصل','gender':'female','style':'سعودية هادية','conversation_mode':'initiative'},[],None)
        content=json.loads(session.request[1]['json']['contents'][0]['parts'][0]['text'])
        self.assertEqual(content['persona_gender'],'female')
        self.assertEqual(content['persona_name'],'فيصل')
        self.assertEqual(content['conversation_mode'],'initiative')
    async def test_multi_message_parsing(self):
        class MultiSession(Session):
            def post(self,url,**kwargs):
                return Response(self.status,{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"messages":["هلا والله","وش مسوي؟"],"text":"هلا والله وش مسوي؟"}'}]}}]})
        provider=Gemini(MultiSession(),'test','model')
        res=await provider.generate({'style':'سعودي'},[],None)
        self.assertEqual(res['messages'],['هلا والله','وش مسوي؟'])
        self.assertEqual(res['text'],'هلا والله وش مسوي؟')
    async def test_refusal_and_quota_failure(self):
        self.assertEqual(await Gemini(Session(finish='SAFETY'),'test','model').generate({'style':'سعودي'},[],None),{'text':'','messages':[]})
        with self.assertRaises(RuntimeError):await Gemini(Session(status=429),'test','model').generate({'style':'سعودي'},[],None)
