// Test-only process preload. Production never imports this module.
const {GameRuntimeFactory}=require('../../gamehost/runtime');
const schedule=GameRuntimeFactory.prototype._scheduleAlarm;
GameRuntimeFactory.prototype._scheduleAlarm=function(room,ms,id){return schedule.call(this,room,Math.min(ms,250),id);};
