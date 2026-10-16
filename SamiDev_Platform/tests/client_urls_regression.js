'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../clients/desktop-electron/main.js'),'utf8');
function configure(url,packaged){
 const context={URL,process:{env:url===undefined?{}:{SAMIDEV_PLATFORM_URL:url}},require(name){assert.equal(name,'electron');return {app:{isPackaged:packaged,whenReady:()=>({then(){}}),on(){}},BrowserWindow:{},session:{},shell:{}};}};
 vm.createContext(context);vm.runInContext(source+';this.result=PLATFORM_URL;',context);return context.result;
}
assert.equal(configure(undefined,false),'http://127.0.0.1:8088/platform/');
assert.equal(configure('https://my-platform.test',true),'https://my-platform.test/platform/');
assert.equal(configure('https://my-platform.test/platform/',true),'https://my-platform.test/platform/');
for(const url of [undefined,'https://game.example.com/platform/','http://remote.test/platform/','http://localhost/platform/','https://u:p@my-platform.test/','https://my-platform.test/?redirect=elsewhere','javascript:alert(1)','https://my-platform.test/unrelated'])assert.throws(()=>configure(url,true));
console.log('CLIENT_URLS_PASS: explicit production URL, HTTPS, no placeholder/default/credential/query destinations');
