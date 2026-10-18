"""TD6HLM: a restored host's low revision must replace the prior generation's snapshot."""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from store import MemoryStore,RedisStore,sanitize_settings


async def verify(store,label):
    rid=(await store.create_room('A',sanitize_settings({'gameId':'crazy8','seats':0}),'node','c1'))['roomId']
    await store.join_room(rid,'B',None,'node','c2')
    await store.runtime_ready(rid,0,'c1',1)
    await store.runtime_ready(rid,1,'c2',1)
    first=await store.claim_authority(rid,'host-old')
    for seat,count in [(0,7),(1,9)]:
        for n in range(count):
            await store.append_move(rid,seat,{'i':f'{seat}-{n}','n':n,'m':{'d':1}})
    old={'n':[7,9],'d':{'won':-1},'phase':'old'}
    await store.set_snapshot(rid,-1,old,16,revision=16,authority_epoch=first['epoch'],authority_shard='host-old')
    second=await store.claim_authority(rid,'host-new',renew=True)
    # Native timeout moves have no player packet in the 16-entry history.
    await store.sync_sequence(rid,[8,10])
    current={'n':[8,10],'d':{'won':-1},'phase':'recovered'}
    await store.set_snapshot(rid,-1,current,16,revision=2,authority_epoch=second['epoch'],authority_shard='host-new')
    assert (await store.resync(rid))['snapshot']==current,label+': restore rewound sequence'
    # Same generation cannot rewind an alarm checkpoint.
    await store.set_snapshot(rid,-1,old,16,revision=1,authority_epoch=second['epoch'],authority_shard='host-new')
    assert (await store.resync(rid))['snapshot']==current
    # Neither the old generation nor a different shard may overwrite it.
    for epoch,shard in [(first['epoch'],'host-old'),(second['epoch'],'host-old')]:
        await store.set_snapshot(rid,-1,old,16,revision=999,authority_epoch=epoch,authority_shard=shard)
        assert (await store.resync(rid))['snapshot']==current
    terminal={'n':[8,10],'d':{'won':-2},'phase':'terminal'}
    await store.set_snapshot(rid,-1,terminal,16,revision=3,authority_epoch=second['epoch'],authority_shard='host-new')
    await store.mark_finished(rid)
    result=await store.resync(rid)
    assert result['snapshot']==terminal
    assert result['sequence']==[8,10] and result['moveCount']==16
    assert (await store.get_room_state(rid))['finished']
    print(json.dumps({'store':label,'ok':True,'historyCount':16,'oldRevision':16,'newRevision':3,'sequence':[8,10],'terminalSnapshotPreserved':True}))


async def main():
    await verify(MemoryStore(),'memory')
    url=os.environ.get('SAMIDEV_TEST_REDIS_URL')
    if url:
        store=RedisStore(url,prefix='uno-epoch-test-'+uuid.uuid4().hex)
        try:await verify(store,'redis')
        finally:
            keys=[key async for key in store.r.scan_iter(store.prefix+':*')]
            if keys:await store.r.delete(*keys)
            await store.r.aclose()


if __name__=='__main__':asyncio.run(main())
