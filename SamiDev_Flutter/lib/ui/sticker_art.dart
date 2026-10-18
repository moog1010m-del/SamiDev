import 'package:flutter/material.dart';

/// Uses independent artwork; maps historical badge URLs without losing ownership.
class StickerArtwork extends StatelessWidget {
  const StickerArtwork({super.key,required this.asset,this.size=24});
  final String asset;
  final double size;
  static String resolve(String value) {
    const badges=['badge_crown','badge_orbit','badge_shell','badge_fox','badge_fire','badge_crystal','badge_leopard','badge_jellyfish'];
    value=value.replaceFirstMapped(RegExp(r'^(/platform/assets/stickers/badge_[a-z]+)-v2\.png$'),(match)=>'${match.group(1)}-v3.png');
    final index=cell(value);
    if(index!=null && index<9)return index<badges.length?'/platform/assets/stickers/${badges[index]}-v3.png':'';
    final old=RegExp(r'^/platform/assets/cosmetics/(badge_(?:shard|ember|moonstone|steward))\.webp$').firstMatch(value);
    return old==null?value:'/platform/assets/stickers/${old.group(1)}-v3.png';
  }
  static int? cell(String value){
    if(value=='/platform/assets/profile/identity/profile-atlas.png#star')return 9;
    final match=RegExp(r'^/platform/assets/stickers/samidev-stickers\.png#cell-([0-8])$').firstMatch(value);
    return match==null?null:int.parse(match.group(1)!);
  }
  @override Widget build(BuildContext context){
    final resolved=resolve(asset);
    if(resolved.isEmpty||resolved=='/platform/assets/profile/raster/palm-swords.webp')return const SizedBox.shrink();
    final index=cell(resolved);
    if(index==null){
      if(!RegExp(r'^/(images|games|platform/assets|room-sprites)/[A-Za-z0-9_./-]+$').hasMatch(resolved)||resolved.contains('..'))return SizedBox(width:size,height:size);
      return Image.asset('assets/runtime$resolved',width:size,height:size,fit:BoxFit.contain);
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
