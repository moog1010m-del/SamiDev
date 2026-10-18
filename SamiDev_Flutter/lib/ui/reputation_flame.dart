import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Shared with profile-details.js: earned reputation, independent of store art.
class ReputationFlame extends StatefulWidget {
  const ReputationFlame({super.key,required this.score,this.size=28});
  final int score;
  final double size;
  static int tier(int score) {
    const thresholds=[0,1,100,500,1000,10000,50000];
    var result=0;
    for(var i=0;i<thresholds.length;i++){if(score>=thresholds[i])result=i;}
    return result;
  }
  @override State<ReputationFlame> createState()=>_ReputationFlameState();
}
class _ReputationFlameState extends State<ReputationFlame> with SingleTickerProviderStateMixin {
  late final AnimationController pulse=AnimationController(vsync:this,duration:const Duration(milliseconds:2400));
  void updateMotion(){
    final media=MediaQuery.maybeOf(context);
    if(ReputationFlame.tier(widget.score)==6 && media?.disableAnimations!=true && media?.accessibleNavigation!=true){
      if(!pulse.isAnimating)pulse.repeat();
    }else{pulse.stop();pulse.value=0;}
  }
  @override void didChangeDependencies(){super.didChangeDependencies();updateMotion();}
  @override void didUpdateWidget(covariant ReputationFlame oldWidget){super.didUpdateWidget(oldWidget);updateMotion();}
  @override void dispose(){pulse.dispose();super.dispose();}
  @override Widget build(BuildContext context)=>ExcludeSemantics(child:SizedBox(
    width:widget.size,height:widget.size*1.2,
    child:AnimatedBuilder(animation:pulse,builder:(context,child)=>CustomPaint(painter:_FlamePainter(ReputationFlame.tier(widget.score),pulse.value))),
  ));
}
class _FlamePainter extends CustomPainter {
  const _FlamePainter(this.tier,this.pulse);
  final int tier;
  final double pulse;
  static const colors=[Color(0xff9aafb1),Color(0xffe4ab63),Color(0xffe98672),Color(0xff69b9ac),Color(0xff6eaff0),Color(0xffa18be0),Color(0xffd781ba)];
  static const halos=[Color(0xffdbe4e5),Color(0xfff5d7a5),Color(0xfff5c0ad),Color(0xffb4e3cd),Color(0xffbae2fc),Color(0xffe1cef9),Color(0xffb9c9ff)];
  @override void paint(Canvas canvas,Size size){
    canvas.save();canvas.scale(size.width/40,size.height/48);
    final halo=Path()..moveTo(20,2)..cubicTo(22,13,35,15,35,29)..cubicTo(35,39,28,45,20,45)..cubicTo(12,45,5,39,5,29)..cubicTo(5,22,9,17,12,13)..cubicTo(12,19,14,21,16,22)..cubicTo(20,16,15,10,20,2)..close();
    canvas.save();
    if(tier==6){final wave=(1-math.cos(pulse*math.pi*2))/2;canvas.translate(20,42);canvas.scale(1-.06*wave,1+.06*wave);canvas.translate(-20,-42);}
    canvas.drawPath(halo,Paint()..color=halos[tier].withValues(alpha:.5));
    if(tier>=5)canvas.drawPath(halo,Paint()..color=colors[tier]..style=PaintingStyle.stroke..strokeWidth=tier==6?1.5:.7);
    canvas.restore();
    final body=Path()..moveTo(21,7)..cubicTo(22,17,32,20,32,30)..cubicTo(32,38,27,43,20,43)..cubicTo(13,43,8,38,8,30)..cubicTo(8,25,10,22,13,18)..cubicTo(13,24,16,26,18,27)..cubicTo(23,20,18,14,21,7)..close();
    canvas.drawPath(body,Paint()..color=colors[tier]);
    final core=Path()..moveTo(21,25)..cubicTo(22,30,27,31,27,36)..cubicTo(27,45.3,13,45.3,13,36)..cubicTo(13,33,15,30,17,28)..cubicTo(17,32,19,33,20,34)..cubicTo(22,31,20,28,21,25)..close();
    canvas.drawPath(core,Paint()..color=const Color(0xfffff4cc));
    if(tier>=4){final sparks=Path()..moveTo(6,8)..lineTo(7,11)..moveTo(32,5)..lineTo(31,9)..moveTo(2,26)..lineTo(4,27)..moveTo(36,19)..lineTo(38,17);canvas.drawPath(sparks,Paint()..color=colors[tier]..strokeWidth=1.6..strokeCap=StrokeCap.round..style=PaintingStyle.stroke);}
    canvas.restore();
  }
  @override bool shouldRepaint(covariant _FlamePainter old)=>old.tier!=tier||old.pulse!=pulse;
}
