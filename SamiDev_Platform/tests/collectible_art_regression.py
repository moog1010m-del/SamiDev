"""Art refresh preserves purchases, moderator scope and old-message compatibility."""
import asyncio,json,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from social_platform import STORE_CATALOG,PlatformService,PlatformError,collectible_availability

async def main():
 rows=json.loads((ROOT/'game/platform/assets/stickers/collection.json').read_text(encoding='utf-8'))['items']
 assert len(rows)==12 and len({r['asset'] for r in rows})==12
 for row in rows:
  assert STORE_CATALOG[row['id']]['asset']==row['asset']
  with Image.open(ROOT/'game'/row['asset'].lstrip('/')) as art:
   assert art.size==(256,256) and art.mode=='RGBA'
   assert art.getchannel('A').getextrema()==(0,255)
 assert STORE_CATALOG['badge_steward']['retired'] is True
 assert STORE_CATALOG['badge_steward']['price']==0
 special=collectible_availability('badge_steward',STORE_CATALOG['badge_steward'])
 assert special['kind']=='moderator' and special['purchasable'] is False
 assert 'مشرفي' in special['label']
 event=collectible_availability('fixture',dict(retired=True,availabilityKind='event',eventName='لقاء اللاعبين'))
 assert event['kind']=='event' and not event['purchasable'] and 'لقاء اللاعبين' in event['label']
 assert collectible_availability('fixture',dict(retired=True))['kind']=='unavailable'
 service=PlatformService()
 user=await service.create_user('art_collector','Test-password-123')
 uid=user['id'];service.mem_users[uid]['coins']='1000'
 await service.grant_store_item(uid,'badge_fox')
 before=await service.store_snapshot(uid)
 await service.equip_store_item(uid,'badge_fox')
 profile=await service.public_profile(uid,uid)
 assert profile['nameBadge']=='badge_fox'
 assert profile['nameBadgeAsset'].endswith('/badge_fox-v2.png')
 owned=next(item for item in profile['showcaseItems'] if item['id']=='badge_fox')
 assert owned['description'] and owned['slot']=='name_badge' and owned['availability']['kind']=='store'
 assert (await service.store_snapshot(uid))['coins']==before['coins']
 await service.buy_store_item(uid,'badge_shell')
 after=await service.store_snapshot(uid)
 assert after['coins']==before['coins']-STORE_CATALOG['badge_shell']['price']
 assert 'badge_fox' in after['inventory'] and 'badge_shell' in after['inventory']
 message=await service.chat_sticker(uid,'badge_shell')
 assert message['stickerAsset'].endswith('/badge_shell-v2.png')
 try:await service.chat_sticker(uid,'badge_crystal')
 except PlatformError:pass
 else:raise AssertionError('unowned art sent')
 print('COLLECTIBLE_ART_PASS: 12 independent alpha assets; ownership; prices; entitlement; chat')
if __name__=='__main__':asyncio.run(main())
