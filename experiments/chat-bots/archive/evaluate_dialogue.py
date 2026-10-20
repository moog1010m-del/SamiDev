"""Opt-in real-model dialogue preview; never joins a room or writes platform messages."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
import aiohttp
from core import Coordinator,Memory,Message,load_config
from gemini import Gemini


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).with_name('config.example.json')))
    parser.add_argument('--enable-api',action='store_true',help='Allow up to six real Gemini requests')
    args=parser.parse_args()
    if not args.enable_api:raise ValueError('Use --enable-api to allow up to six real model requests')
    config=load_config(args.config)
    dialogue=['السلام عليكم','الحمد لله، توي راجع من الدوام','كان اليوم طويل، قلت أروق شوي','أتابع يوتيوب غالبًا','أحب المقاطع التقنية','فيه ترند جديد اليوم؟']
    with tempfile.TemporaryDirectory() as directory:
        memory=Memory(Path(directory)/'preview.sqlite')
        try:
            async with aiohttp.ClientSession() as session:
                provider=Gemini(session,os.environ.get('GEMINI_API_KEY',''),os.environ.get('GEMINI_MODEL',''))
                engine=Coordinator({**config,'daily_model_calls':min(6,config['daily_model_calls'])},memory,[],provider)
                engine.identities={p['id']:{'name':p['name'],'kind':'bot','persona_id':p['id'],'gender':p.get('gender','unspecified')} for p in config['profiles']}
                for index,text in enumerate(dialogue):
                    message=Message(str(index),'preview-user',text);engine.ingest(message)
                    reply=await engine.respond(message)
                    print(json.dumps({'input':text,'speaker':reply.speaker if reply else None,'reply':reply.text if reply else None,'source':reply.reason if reply else None},ensure_ascii=False),flush=True)
                    if reply:
                        memory.add(config['room'],Message('reply-'+str(index),reply.speaker,reply.text))
                        # Preview advances dialogue turns immediately, with no live send or cooldown.
                        engine.turn+=1
        finally:memory.close()


if __name__=='__main__':
    try:asyncio.run(main())
    except Exception as error:
        print('DIALOGUE_PREVIEW_FAILED: '+type(error).__name__)
        raise SystemExit(1)
