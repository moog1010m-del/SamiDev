import unittest
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
        return Response(self.status,{'candidates':[{'finishReason':self.finish,'content':{'parts':[{'text':'{"text":"هلا والله"}'}]}}]})
class GeminiTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_request_and_key_not_in_url(self):
        session=Session();provider=Gemini(session,'test-only-secret','test-model')
        self.assertEqual(await provider.generate({'style':'سعودي'},[],'الكيرم'),'هلا والله')
        url,request=session.request
        self.assertNotIn('test-only-secret',url);self.assertFalse(request['allow_redirects'])
        self.assertEqual(request['json']['generationConfig']['responseMimeType'],'application/json')
    async def test_refusal_and_quota_failure(self):
        self.assertEqual(await Gemini(Session(finish='SAFETY'),'test','model').generate({'style':'سعودي'},[],None),'')
        with self.assertRaises(RuntimeError):await Gemini(Session(status=429),'test','model').generate({'style':'سعودي'},[],None)
