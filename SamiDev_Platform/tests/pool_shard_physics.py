"""Concurrent real pool breaks on authenticated, isolated production shards.
Accounts are fixture-seeded: this measures gameplay, not registration throughput.
"""
import asyncio,json,time,os
from pathlib import Path
import aiohttp
from realtime_cluster_fixture import Cluster,receive

async def main():
    cluster=Cluster(gateways=2,hosts=2);sockets=[]
    try:
        await cluster.start();cookies=await cluster.seed(32)
        async with aiohttp.ClientSession() as client:
            pairs=[];rooms=[]
            for i in range(16):
                pair=[await client.ws_connect(cluster.urls[j%2]+'/ws',headers=cookies[j]) for j in [i*2,i*2+1]];sockets.extend(pair)
                await pair[0].send_json({'type':'create_room','settings':{'gameId':'pool','gameType':0}});created=await receive(pair[0],{'created'});rid=created['roomId']
                await pair[1].send_json({'type':'join_room','roomId':rid});await receive(pair[1],{'joined'})
                await asyncio.gather(*(receive(ws,{'start'}) for ws in pair))
                await asyncio.gather(*(ws.send_json({'type':'runtime_ready'}) for ws in pair))
                await asyncio.gather(*(receive(ws,{'begin_match'}) for ws in pair))
                await pair[0].send_json({'type':'resync'});state=await receive(pair[0],{'resync_state'})
                await pair[0].send_json({'type':'move','packet':{'i':'ready-load','n':state['sequence'][0],'m':{'__ready':1}}})
                ready=await receive(pair[0],{'move'});await receive(pair[1],{'move'})
                pairs.append((pair,ready['packet']['n']+1));rooms.append(rid)
            async def shot(index,pair,seq):
                began=time.perf_counter()
                await pair[0].send_json({'type':'move','packet':{'i':'physical-burst-'+str(index),'n':seq,'m':{'a':1,'st':.8,'an':-1.5707963267948966,'sp':[0,0]}}})
                replies=await asyncio.gather(*(receive(ws,{'move'}) for ws in pair))
                assert replies[0]['packet']==replies[1]['packet']
                assert replies[0]['reveal']['data']==replies[1]['reveal']['data']
                assert replies[0]['reveal']['pool']==replies[1]['reveal']['pool']
                assert 'frames' not in replies[0]['reveal']
                return {'latencyMs':(time.perf_counter()-began)*1000,'clientMessageBytes':len(json.dumps(replies[0],separators=(',',':')).encode())}
            samples=await asyncio.gather(*(shot(i,*value) for i,value in enumerate(pairs)))
            metrics=[]
            for host in cluster.hosts:
                async with client.get(host+'/v1/metrics',headers={'X-SamiDev-Service-Key':cluster.secret}) as response:metrics.append(await response.json())
            owners=[await cluster.r.hget(cluster.prefix+'r:room:'+rid,'authorityShard') for rid in rooms]
            durations=sorted(x['latencyMs'] for x in samples)
            report={'ok':True,'players':32,'matches':16,'simultaneousFullPhysicsBreaks':16,'configuredHosts':2,'roomsPerHost':[owners.count(host) for host in cluster.hosts],'latencyMs':{'p50':durations[len(durations)//2],'p95':durations[-1]},'clientMessageBytes':{'min':min(x['clientMessageBytes'] for x in samples),'max':max(x['clientMessageBytes'] for x in samples)},'hostMoveMs':[m['recentMoveMs'] for m in metrics],'note':'Local synchronized burst; seeded accounts; not a 10,000-player capacity certification'}
            output=os.getenv('SAMIDEV_TEST_ARTIFACTS','/tmp/samidev-pool-contract');Path(output).mkdir(parents=True,exist_ok=True);Path(output,'shard-physics.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:
        for ws in sockets:await ws.close()
        await cluster.close()

if __name__=='__main__':asyncio.run(main())
