"""Fair scheduling from real match counts; ongoing games are never interrupted."""
from collections import Counter


class Rotation:
    def __init__(self):self.assigned={};self.serial=0

    def order(self,bots):
        return sorted(bots,key=lambda bot:(bot.get('poolPlayed',0),self.assigned.get(bot['id'],0),bot['id']))

    def selected(self,bot):
        self.serial+=1;self.assigned[bot['id']]=self.serial

    def pair(self,free,bots,jobs,kinds,room,target=40,reserve=10):
        active=[bot for bot in bots if bot['room']==room and bot['enabled'] and not bot.get('banned')]
        counts=Counter(kinds.get(bot['id']) for bot in active if bot['id'] in jobs)
        available=[bot for bot in free if bot['room']==room]
        limit=min(target,max(0,len(active)-reserve))
        reserve_needed=max(0,reserve-counts['human'])
        if counts['selfplay']+2>limit or len(available)-2<reserve_needed:return None
        return self.order(available)[:2] if len(available)>=2 else None

    def prune(self,bots):
        ids={bot['id'] for bot in bots};self.assigned={uid:value for uid,value in self.assigned.items() if uid in ids}
