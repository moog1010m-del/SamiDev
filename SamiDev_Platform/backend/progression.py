"""Original SamiDev victory ranks. Cosmetics never alter competitive progression."""
from games import GAMES

RANK_NAMES = ('بداية', 'وميض', 'شعاع', 'نجم', 'مدار', 'شهاب', 'مجرة', 'سديم', 'قطب', 'قمة')


def wins_for_level(level):
    level = max(1, min(100, int(level)))
    return 5 * (level - 1) * level // 2


def progression(wins):
    wins = max(0, int(wins))
    level = 1
    while level < 100 and wins >= wins_for_level(level + 1):
        level += 1
    floor = wins_for_level(level)
    ceiling = wins_for_level(level + 1) if level < 100 else floor
    earned = wins - floor
    needed = ceiling - floor
    return dict(level=level, rankName=RANK_NAMES[(level - 1) // 10],
                rankAsset=f'/platform/assets/ranks/level-{level:03}.svg',
                progress=1 if level == 100 else min(1, earned / needed),
                winsInLevel=earned, winsToNextLevel=max(0, ceiling - wins),
                levelStartWins=floor, nextLevelWins=None if level == 100 else ceiling,
                maxLevel=100)


def statistics(game, raw):
    wins = max(0, int(raw.get('wins') or 0))
    played = max(wins, int(raw.get('played') or 0))
    draws = min(max(0, int(raw.get('draws') or 0)), played - wins)
    return dict(gameId=game, name=GAMES[game]['name'],
                icon=f'/room-sprites/{dict(pool="pool", carrom="carrom", tablesoccer="football", crazy8="cards")[game]}.png',
                wins=wins, played=played, draws=draws, losses=played - wins - draws,
                **progression(wins))
