import 'package:flutter/material.dart';

/// Crops a single cell at render time from the bundled original 3x3 atlas.
class StickerArtwork extends StatelessWidget {
  const StickerArtwork({super.key,required this.asset,this.size=24});
  final String asset;
  final double size;
  static int? cell(String value){
    if(value=='/platform/assets/profile/identity/profile-atlas.png#star')return 9;
    final match=RegExp(r'^/platform/assets/stickers/samidev-stickers\.png#cell-([0-8])$').firstMatch(value);
    return match==null?null:int.parse(match.group(1)!);
  }
  @override Widget build(BuildContext context){
    if(asset.isEmpty||asset=='/platform/assets/profile/raster/palm-swords.webp')return const SizedBox.shrink();
    final index=cell(asset);
    if(index==null){
      if(!RegExp(r'^/(images|games|platform/assets|room-sprites)/[A-Za-z0-9_./-]+$').hasMatch(asset)||asset.contains('..'))return SizedBox(width:size,height:size);
      return Image.asset('assets/runtime$asset',width:size,height:size,fit:BoxFit.contain);
    }
    final cols=index==9?4:3,rows=index==9?2:3;
    final col=index==9?0:index%3,row=index==9?0:index~/3;
    final sheet=index==9?'assets/runtime/platform/assets/profile/identity/profile-atlas.png':'assets/runtime/platform/assets/stickers/samidev-stickers.png';
    return SizedBox(width:size,height:size,child:ClipRect(child:OverflowBox(
      alignment:Alignment.topLeft,minWidth:size*cols,maxWidth:size*cols,minHeight:size*rows,maxHeight:size*rows,
      child:Transform.translate(offset:Offset(-col*size,-row*size),child:Image.asset(
        sheet,width:size*cols,height:size*rows,fit:BoxFit.fill)))));
  }
}
