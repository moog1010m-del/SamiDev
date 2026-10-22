// Real font measurement, independent rectangle assertions for the shared layout.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {createCanvas}=require('@napi-rs/canvas');
require('../design/avatar-layout-v36.js');
const context=createCanvas(1,1).getContext('2d');context.font='40px sans-serif';
function node(w=0,h=0){return {width:w,height:h,x:0,y:0,anchorX:.5,anchorY:.5,visible:true,resize(w,h){this.width=w;this.height=h},position(x,y){this.x=x;this.y=y}}}
function rect(n,parent={x:0,y:0}){return {x:parent.x+n.x-n.width*n.anchorX,y:parent.y+n.y-n.height*n.anchorY,w:n.width,h:n.height}}
function overlap(a,b){return a.x<b.x+b.w-.01&&a.x+a.w>b.x+.01&&a.y<b.y+b.h-.01&&a.y+a.h>b.y+.01}
let count=0;
for(const align of ['BELOW','ABOVE','LEFT','RIGHT'])for(const text of ['888','٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩','لاعب باسم عربي طويل جدًا','Moon 🌙 Player 123456789'])for(const badgeWidth of [0,28,64]){
 const a={idContainer:node(),badgeContainer:node(badgeWidth,32),nameText:node(),nameTextMeasure:node(),_activeIndicator:node(),localTurnPill:node(200,64),ownerIndicator:node(),_imageRadius:50,nameMargin:0,maxNameWidth:240,nameAlign:align,oldNameTextContents:text,checkOwnerBadgeVisibility(){this.ownerIndicator.visible=true}};
 a.nameText.fontSize=40;a.nameTextMeasure._update=function(){this.width=context.measureText(this.text).width};
 SamiDevAvatarLayout.position(a);
 const row=rect(a.idContainer),dot=rect(a._activeIndicator),crown=rect(a.ownerIndicator);
 assert(!overlap(row,dot),'presence must not overlap name row');assert(!overlap(row,crown),'crown must not overlap name row');assert(!overlap(dot,crown),'presence must not overlap crown');
 assert(a.idContainer.width<=240.01,'name and badges must fit their budget');
 assert(a.nameText.x>=badgeWidth*a.badgeContainer.scaleX,'badge/name gap');
 const nameBounds=rect(a.nameText,{x:row.x,y:row.y});nameBounds.w=a.nameTextMeasure.width;nameBounds.h=40;nameBounds.y=a.idContainer.y-a.idContainer.anchorY*a.idContainer.height+a.nameText.y-20;
 assert.equal(a.localTurnPill.visible,false,'legacy turn pill is disabled; dedicated HUD draws the badge');
 a.maxNameWidth=120;SamiDevAvatarLayout.position(a);const short=a.nameText.text;
 assert(a.idContainer.width<=120.01,'badges and long name also fit narrow side seats');
 a.maxNameWidth=240;SamiDevAvatarLayout.position(a);assert(a.nameText.text.length>=short.length,'name restores after resize');
 count++;
}
console.log('avatar_layout_v36: OK ('+count+' measured name / badge / alignment cases; resize restoration)');
