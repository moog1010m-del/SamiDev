import 'package:flutter/material.dart';

/// Preserve the engine's viewport while the keyboard covers its lower part.
/// Chat history is an overlay and never reserves a second empty panel.
class GameViewport extends StatefulWidget {
  const GameViewport({super.key,required this.child,this.overlay,this.dim=false,this.active=true});
  final Widget child;
  final Widget? overlay;
  final bool dim,active;
  @override State<GameViewport> createState()=>_GameViewportState();
}
class _GameViewportState extends State<GameViewport> {
  double height=0,width=0;
  @override Widget build(BuildContext context)=>LayoutBuilder(builder:(context,box){
    final keyboard=MediaQuery.viewInsetsOf(context).bottom;
    if(height==0||widget.active&&keyboard==0){height=box.maxHeight;}else if(widget.active&&width!=box.maxWidth){height=box.maxHeight+keyboard;}
    width=box.maxWidth;
    return Stack(fit:StackFit.expand,children:[
      AbsorbPointer(absorbing:widget.dim,child:ClipRect(child:OverflowBox(alignment:Alignment.topCenter,minHeight:height,maxHeight:height,
        child:SizedBox(height:height,width:box.maxWidth,child:widget.child)))),
      if(widget.overlay!=null)Positioned(bottom:0,left:0,right:0,child:widget.overlay!),
    ]);
  });
}
