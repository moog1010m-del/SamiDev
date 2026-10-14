"""Capture one real pool match through the PRIVATE GameHost service API.

Enable SAMIDEV_POOL_RECORD_DIR on each GameHost first. This tool never exports the
service key or account credentials. Start it while clients wait before the break.
Ctrl+C stops cleanly and downloads the captured interval; a normal match ends it
automatically. Recordings survive the tool disconnecting, up to the host limits.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import time
import uuid

import aiohttp


async def capture(hosts, room, output, key, *, seconds=21600, poll=2, wait=120):
    if output.exists(): raise ValueError('output already exists; choose a new filename')
    headers={'X-SamiDev-Service-Key':key}
    host=None;record=None
    async with aiohttp.ClientSession(headers=headers,timeout=aiohttp.ClientTimeout(total=30)) as session:
        async def command(url, action):
            async with session.post(url+'/v1/recording/'+action,json={'roomId':room}) as response:
                data=await response.json()
                if response.status==404:return None
                if response.status!=200:raise RuntimeError('recording service: '+str(data.get('code','HTTP_'+str(response.status))))
                return data
        began=time.monotonic()
        while host is None:
            for candidate in hosts:
                result=await command(candidate,'start')
                if result:host=candidate;record=result;break
            if host:break
            if time.monotonic()-began>=wait:raise TimeoutError('room not loaded; both players must join before the first shot')
            await asyncio.sleep(poll)
        print(json.dumps({'recordingStarted':True,'recordingId':record['recordingId'],'room':room,'output':str(output)},ensure_ascii=False),flush=True)
        print('Recording is active. Play normally; match end or Ctrl+C downloads the file.',flush=True)
        try:
            began=time.monotonic()
            while record['active'] and time.monotonic()-began<seconds:
                await asyncio.sleep(poll)
                record=await command(host,'status')
                if not record:raise RuntimeError('recording disappeared; host may have restarted')
        except asyncio.CancelledError:
            pass
        finally:
            stopped=await command(host,'stop')
            if not stopped:raise RuntimeError('cannot seal recording')
            output.parent.mkdir(parents=True,exist_ok=True)
            temporary=output.with_name(output.name+'.'+uuid.uuid4().hex+'.partial')
            total=0
            try:
                async with session.get(host+'/v1/recording/'+stopped['recordingId']) as response:
                    if response.status!=200:raise RuntimeError('download failed: HTTP '+str(response.status))
                    with temporary.open('xb') as file:
                        os.chmod(temporary,0o600)
                        async for chunk in response.content.iter_chunked(65536):
                            total+=len(chunk)
                            if total>65*1024*1024:raise RuntimeError('recording too large')
                            file.write(chunk)
                # A link publishes the completed file without overwriting an existing one.
                os.link(temporary,output);temporary.unlink()
            finally:
                if temporary.exists():temporary.unlink()
            print(json.dumps({'saved':str(output),'bytes':total,'events':stopped['events'],'complete':stopped['complete']}),flush=True)
            if not stopped['complete']:raise RuntimeError('incomplete recording saved for diagnosis; replay will reject it')
            return output


def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--room',required=True)
    parser.add_argument('--hosts',default=os.getenv('SAMIDEV_GAMEHOST_URLS') or os.getenv('SAMIDEV_GAMEHOST_URL','http://127.0.0.1:8091'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=21600)
    parser.add_argument('--wait-seconds',type=float,default=120)
    args=parser.parse_args();room=args.room.strip().upper()
    if not re.fullmatch(r'[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}',room):parser.error('invalid room code')
    key=os.getenv('SAMIDEV_GAMEHOST_SERVICE_KEY')
    if not key:parser.error('set the existing service key through the environment; do not put it in the command')
    if args.seconds<=0 or args.seconds>21600 or args.wait_seconds<=0:parser.error('seconds must be 0..21600; wait-seconds positive')
    try:asyncio.run(capture([s.strip().rstrip('/') for s in args.hosts.split(',') if s.strip()],room,args.output,key,seconds=args.seconds,wait=args.wait_seconds))
    except KeyboardInterrupt:pass


if __name__=='__main__':cli()
