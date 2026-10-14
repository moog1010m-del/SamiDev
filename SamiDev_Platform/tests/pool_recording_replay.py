"""Capture real authorized inputs + a native alarm, then replay on fresh rooms.

The source demo ends by resignation; it is a transport/physics capture fixture,
not a recording of the user's eventual game. No outcomes or scores are forged.
"""
import argparse
import asyncio
from collections import Counter,defaultdict
import json
import math
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

import aiohttp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pool_match_record import capture
from pool_match_replay import Actor,Replay,load_recording,require
from realtime_cluster_fixture import Cluster


async def source(output):
    cluster=Cluster(gateways=1,hosts=1);actors=[];capture_task=None
    previous=os.environ.get('SAMIDEV_POOL_RECORD_DIR');os.environ['SAMIDEV_POOL_RECORD_DIR']=str(output/'private-source')
    try:
        await cluster.start()
        async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(),connector=aiohttp.TCPConnector(limit=0)) as session:
            run=SimpleNamespace(cluster=cluster,name='ps'+secrets.token_hex(4),account_sem=asyncio.Semaphore(2),session=session,latencies=defaultdict(list),counts=Counter())
            actors=[Actor(run,i) for i in range(2)]
            await asyncio.gather(*(a.account() for a in actors));await asyncio.gather(*(a.connect() for a in actors))
            await actors[0].ws.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':7}})
            await actors[0].wait(lambda:actors[0].assignment is not None);rid=actors[0].assignment['roomId']
            await actors[1].ws.send_json({'type':'join_room','roomId':rid})
            await asyncio.gather(*(a.wait(lambda a=a:a.start is not None) for a in actors))
            async with session.post(cluster.hosts[0]+'/v1/recording/start',json={'roomId':rid}) as response:require(response.status==401,'recording start lacks service authentication')
            async with session.post(cluster.hosts[0]+'/v1/recording/start',json={'roomId':rid},headers={'X-SamiDev-Service-Key':cluster.secret}) as response:
                require(response.status==200,'source recording did not start');start=await response.json()
            async with session.get(cluster.hosts[0]+'/v1/recording/'+start['recordingId']) as response:require(response.status==401,'recording export lacks service authentication')
            capture_task=asyncio.create_task(capture(cluster.hosts,rid,output/'sample.jsonl',cluster.secret,seconds=60,poll=.1))
            await asyncio.gather(*(a.ws.send_json({'type':'runtime_ready'}) for a in actors))
            await asyncio.gather(*(a.wait(lambda a=a:a.begun) for a in actors))
            # Let native Ready alarm fire (10s). Replay must observe it naturally,
            # never send the server-only a:5 action from a client.
            await asyncio.gather(*(a.wait(lambda a=a:bool(a.alarms),timeout=20) for a in actors))
            counter=0
            async def move(seat,data):
                nonlocal counter
                counter+=1;packet_id='private-cookie-not-for-export-'+str(counter)
                await actors[seat].ws.send_json({'type':'move','packet':{'i':packet_id,'n':actors[seat].state['sequence'][seat],'m':data}})
                await asyncio.gather(*(a.wait(lambda a=a:packet_id in a.moves) for a in actors))
                require(actors[0].state==actors[1].state,'source client results differ')
                await asyncio.sleep(.15)
            for shot in range(2):
                seat=actors[0].state['turn'][0];await move(seat,{'__ready':1})
                balls=actors[0].state['pool']['balls'];cue=balls[0];target=next(b for b in balls[1:] if not b[3] and b[0]!=8)
                angle=-math.pi/2 if shot==0 else math.atan2(target[2]-cue[2],target[1]-cue[1])+.12
                await move(seat,{'a':1,'st':.8 if shot==0 else .2,'an':angle,'sp':[0,0]})
            await move(1,{'a':0})
            path=await capture_task;capture_task=None
            header,events,end=load_recording(path)
            require(end['reason']=='game_over' and end['state']['gameOver'],'source did not end normally')
            require(sum(e['type']=='alarm' for e in events)>=1,'missing native alarm')
            require(sum(e['type']=='command' and e['input'].get('a')==1 for e in events)==2,'missing physical source shots')
            raw=path.read_text()
            for value in [cluster.secret,rid,'private-cookie-not-for-export',*(a.cookie for a in actors),*(a.username for a in actors)]:require(value not in raw,'recording leaked identity/credential metadata')
            print(json.dumps({'captured':True,'commands':sum(e['type']=='command' for e in events),'alarms':sum(e['type']=='alarm' for e in events),'privateFieldsAbsent':True}),flush=True)
            return path
    finally:
        if capture_task:capture_task.cancel();await asyncio.gather(capture_task,return_exceptions=True)
        await asyncio.gather(*(a.close() for a in actors),return_exceptions=True)
        await cluster.close()
        if previous is None:os.environ.pop('SAMIDEV_POOL_RECORD_DIR',None)
        else:os.environ['SAMIDEV_POOL_RECORD_DIR']=previous


async def main(args):
    args.output.mkdir(parents=True,exist_ok=True)
    recording=await source(args.output)
    config=SimpleNamespace(recording=recording,players=args.players,gateways=args.gateways,hosts=args.hosts,account_concurrency=12,room_concurrency=32,
        spread_seconds=0,max_p95_ms=250,max_lateness_ms=1000,allow_engine_change=False,output=args.output/'replay')
    return await Replay(config).execute()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--players',type=int,default=4)
    parser.add_argument('--hosts',type=int,default=2);parser.add_argument('--gateways',type=int,default=2)
    parser.add_argument('--output',type=Path,default=Path('/tmp/samidev-recording-test'))
    args=parser.parse_args()
    raise SystemExit(asyncio.run(main(args)))
