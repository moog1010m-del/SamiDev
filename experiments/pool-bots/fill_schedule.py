"""One confirmed bot join at a time; elapsed waits never cause a burst."""
import time

SUPPORTED_MODES={0:2,1:4,2:4,4:4,5:4,6:3,7:2}
MULTI_DELAYS=(60,30,15,10)


def waiting_room(room):
    settings=room.get('settings') or {}
    capacity=room.get('capacity');occupied=room.get('occupied',0)
    game=settings.get('gameId')
    supported=(game=='pool' and SUPPORTED_MODES.get(settings.get('gameType',0))==capacity) or (game=='carrom' and capacity in (2,4)) or (game=='crazy8' and capacity in (2,3,4,6))
    return supported and not room.get('started') and not room.get('finished') and 0<occupied<capacity


class FillSchedule:
    def __init__(self):self.joins={}

    def confirmed(self,rid,now=None):
        count,_=self.joins.get(rid,(0,None))
        self.joins[rid]=(count+1,time.time() if now is None else now)

    def eligible(self,room,two_player_delay,now=None,scale=1):
        if not waiting_room(room):return False
        now=time.time() if now is None else now
        if room['capacity']==2:return now-room.get('createdAt',0)/1000>=two_player_delay
        count,last=self.joins.get(room['roomId'],(0,None))
        delay=MULTI_DELAYS[min(count,len(MULTI_DELAYS)-1)]
        baseline=room.get('createdAt',0)/1000 if last is None else last
        return now-baseline>=delay*scale

    def prune(self,rooms):
        waiting={room['roomId'] for room in rooms if waiting_room(room)}
        self.joins={rid:value for rid,value in self.joins.items() if rid in waiting}
