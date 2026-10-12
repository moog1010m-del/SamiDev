(() => {
  'use strict';
  const games = {
    pool:{id:'pool',name:'البلياردو',title:'SamiDev Pool',entry:'/games/pool/index.html',root:'/games/pool/'},
    carrom: {id:'carrom', name:'الكيرم', title:'SamiDev Carrom', entry:'/index.html', root:'/'},
    tablesoccer: {id:'tablesoccer', name:'كرة الطاولة', title:'SamiDev Table Soccer', entry:'/games/tablesoccer/index.html', root:'/games/tablesoccer/'},
    crazy8: {id:'crazy8', name:'أونو', title:'SamiDev Uno', entry:'/games/crazy8/index.html', root:'/games/crazy8/'}
  };
  const current = () => Object.values(games).find(g => g.id!=='carrom' && location.pathname.startsWith(g.root)) || games.carrom;
  const get = id => games[id] || games.carrom;
  const settings = (q, id=current().id) => {
    if (id==='pool') return {gameId:'pool',gameType:0,players:0,live:1,break:0,trickShots:0};
    if (id==='crazy8') return {gameId:id, seats:Number(q.get('seats')??2), live:Number(q.get('live')??1), special:Number(q.get('special')??0)};
    if (id==='tablesoccer') return {gameId:id, players:Number(q.get('players')??0), live:Number(q.get('live')??0), goalsToWin:Number(q.get('goalsToWin')??1), passes:Number(q.get('passes')??0)};
    return {gameId:id, players:Number(q.get('players')??0), live:Number(q.get('live')??1), gamemode:Number(q.get('gamemode')??0), break:Number(q.get('break')??0)};
  };
  const cardSeats = ['لاعبان','3 لاعبين','4 لاعبين','6 لاعبين','فريقان 2 ضد 2'];
  const cardSpecial = ['أساسية','كل الأوراق الخاصة','درع','كشف الأوراق','الأحمر','الأزرق'];
  const label = value => {
    if(value?.gameId==='pool')return 'البلياردو · 8 كرات · لاعب ضد لاعب';
    if (value?.gameId==='crazy8') return `أونو · ${cardSeats[Number(value.seats)??2]||cardSeats[2]} · ${cardSpecial[Number(value.special)||0]}`;
    if (value?.gameId==='tablesoccer') return `كرة الطاولة · ${Number(value.live)===1?'متزامن':'تناوب'} · ${[2,3,5][Number(value.goalsToWin)||0]} أهداف`;
    return `الكيرم · ${['Classic','Pool','Freestyle 120','Freestyle 160','Freestyle 210'][Number(value?.gamemode)||0]}`;
  };
  window.SamiDevGames = {games, current, get, settings, label, cardSeats, cardSpecial};
})();
