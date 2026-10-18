"""Inspect or provision the managed game accounts through the existing admin API."""
import argparse
import asyncio
from collections import Counter
import json
import os
from urllib.parse import urlsplit
import aiohttp


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--apply',action='store_true',help='Create missing accounts up to 50 per room')
    args=parser.parse_args();base=args.base_url.rstrip('/');url=urlsplit(base)
    if url.username or url.password or url.query or url.fragment or url.path or not url.hostname:
        raise ValueError('Use an origin URL without credentials or path')
    if url.scheme!='https' and not(url.scheme=='http' and url.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('HTTPS required outside localhost')
    token=os.environ.get('PLAZR_BOT_ADMIN_SESSION')
    if not token:raise ValueError('Set PLAZR_BOT_ADMIN_SESSION securely in the environment')
    async with aiohttp.ClientSession(cookies={'samidev_session':token},headers={'Origin':base},timeout=aiohttp.ClientTimeout(total=120)) as session:
        async def request(method,body=None):
            async with session.request(method,base+'/api/admin/bots',json=body,allow_redirects=False) as response:
                if response.status!=200:raise RuntimeError('Bot admin API returned HTTP '+str(response.status)+'; verify the running checkout and admin session')
                data=await response.json()
                if data.get('ok') is not True:raise RuntimeError('Bot admin API rejected the request')
                return data
        await request('GET')
        if args.apply:
            result=await request('POST',{'targetPerRoom':50,'enabled':True})
            print(json.dumps({'created':result['created']}))
        state=await request('GET');rows=state['bots']
        counts=Counter(row['room'] for row in rows)
        online=Counter(row['room'] for row in rows if row.get('online'))
        print(json.dumps({'accountsPerRoom':dict(counts),'onlinePerRoom':dict(online),'playWorker':state.get('playWorker',{})},ensure_ascii=False))
        if args.apply and any(counts[room['id']]<50 for room in state['communities']):
            raise RuntimeError('Roster verification failed: a room has fewer than 50 accounts')


if __name__=='__main__':
    try:asyncio.run(main())
    except Exception as error:
        print(type(error).__name__+': '+str(error) if isinstance(error,(ValueError,RuntimeError)) else type(error).__name__)
        raise SystemExit(1)
