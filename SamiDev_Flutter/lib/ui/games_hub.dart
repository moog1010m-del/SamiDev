import 'package:flutter/material.dart';
import 'community_hub.dart';
import 'profile_details.dart';

class QuickMode {
  const QuickMode(this.id,this.title,this.description,this.query);
  final String id,title,description;
  final Map<String,String> query;
}
class GameCardData {
  const GameCardData(this.id,this.name,this.asset,this.color,this.description,this.modes);
  final String id,name,asset,description;
  final Color color;
  final List<QuickMode> modes;
}
const supportedGames=<GameCardData>[
  GameCardData('pool','البلياردو','pool',Color(0xff156a5b),'أنماط متعددة وطاولة واحدة',[
    QuickMode('pool-eight','إيت بول','لاعبان · قواعد إيت بول',{'gameType':'0'}),
    QuickMode('pool-nine','ناين بول','لاعبان · كرات بالترتيب',{'gameType':'3'}),
    QuickMode('pool-free','قيم بول','لاعبان · أول من يسجل ٨ كرات',{'gameType':'7'}),
    QuickMode('pool-teams','إيت بول · فريقان','٤ لاعبين · بالتناوب',{'gameType':'1'}),
    QuickMode('pool-three','الثلاثي','٣ لاعبين · لكل لاعب مجموعته',{'gameType':'6'}),
  ]),
  GameCardData('carrom','الكيرم','carrom',Color(0xff8f5b35),'خشب دافئ وضربات دقيقة',[
    QuickMode('carrom-classic','كلاسيك','لاعبان · قواعد الكيرم الأساسية',{'players':'0','gamemode':'0','live':'1'}),
  ]),
  GameCardData('crazy8','بلازر أونو','cards',Color(0xff745190),'ألوان، بطاقات وتحدٍ جديد',[
    QuickMode('uno-two','مباراة ثنائية','لاعبان · البطاقات الأساسية',{'seats':'0','special':'0','live':'1'}),
  ]),
  GameCardData('tablesoccer','كرة الطاولة','football',Color(0xff305f91),'مرّر، سدّد ونافس',[
    QuickMode('football-two','مباراة ثنائية','لاعبان · ٣ أهداف · تناوب الأدوار',{'players':'0','goalsToWin':'1','live':'0'}),
  ]),
];

/// Native discovery; launches the existing authenticated game gateway and room runtime.
class GamesHub extends StatefulWidget {
  const GamesHub({super.key,required this.onGame,this.user,this.onSelectionChanged});
  final Future<void> Function(String game,Map<String,String> query) onGame;
  final VoidCallback? onSelectionChanged;
  final Map<String,dynamic>? user;
  @override State<GamesHub> createState()=>GamesHubState();
}
class GamesHubState extends State<GamesHub> {
  GameCardData? selected;
  String filter='all';
  bool opening=false;
  bool back(){if(selected==null)return false;setState(()=>selected=null);widget.onSelectionChanged?.call();return true;}
  void choose(GameCardData game){setState(()=>selected=game);widget.onSelectionChanged?.call();}
  Future<void> launch(QuickMode mode)async{
    if(opening||selected==null)return;
    setState(()=>opening=true);
    try{await widget.onGame(selected!.id,{'online':'1','action':'quick','community':'square','preset':mode.id,...mode.query});}
    on StateError{/* Entry failure is already shown by the host. */}
    finally{if(mounted)setState(()=>opening=false);}
  }
  Future<void> privateMatch()async{
    if(opening||selected==null)return;
    final config=await showModalBottomSheet<Map<String,String>>(context:context,isScrollControlled:true,useSafeArea:true,builder:(_)=>CreateMatchSheet(initialGame:selected!.id));
    if(config==null||!mounted)return;
    setState(()=>opening=true);
    try{await widget.onGame(config['game']!,{'online':'1','action':'create','community':'square',...config});}
    on StateError{/* Entry failure is already shown by the host. */}
    finally{if(mounted)setState(()=>opening=false);}
  }
  Widget artwork(GameCardData game,{double size=110})=>Image.asset('assets/runtime/room-sprites/${game.asset}.png',width:size,height:size,fit:BoxFit.contain,errorBuilder:(_,error,stack)=>Icon(Icons.sports_esports_outlined,size:size*.6,color:Colors.white70));
  Widget gameCard(GameCardData game)=>Semantics(button:true,label:'فتح ${game.name}',child:Material(color:game.color,borderRadius:BorderRadius.circular(20),clipBehavior:Clip.antiAlias,child:InkWell(onTap:()=>choose(game),child:Container(decoration:BoxDecoration(gradient:LinearGradient(begin:Alignment.topRight,end:Alignment.bottomLeft,colors:[game.color,Color.lerp(game.color,Colors.black,.6)!])),padding:const EdgeInsets.all(12),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
    Expanded(child:Center(child:artwork(game))),const SizedBox(height:5),Text(game.name,style:const TextStyle(color:Colors.white,fontSize:18,fontWeight:FontWeight.w700)),const SizedBox(height:3),Text(game.description,style:const TextStyle(color:Colors.white70,fontSize:11),maxLines:2),
  ])))));
  Widget modeRow(GameCardData game,QuickMode mode)=>Padding(padding:const EdgeInsets.symmetric(horizontal:16,vertical:18),child:Row(children:[
    Container(width:46,height:46,padding:const EdgeInsets.all(4),decoration:BoxDecoration(color:game.color.withValues(alpha:.15),borderRadius:BorderRadius.circular(13)),child:artwork(game,size:38)),const SizedBox(width:12),
    Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(mode.title,style:const TextStyle(fontSize:17,fontWeight:FontWeight.w700)),const SizedBox(height:5),Text(mode.description,style:TextStyle(fontSize:12,height:1.5,color:Theme.of(context).colorScheme.onSurfaceVariant))])),const SizedBox(width:10),
    FilledButton(onPressed:opening?null:()=>launch(mode),style:FilledButton.styleFrom(backgroundColor:const Color(0xff247d73),foregroundColor:Colors.white,padding:const EdgeInsets.symmetric(horizontal:18,vertical:10)),child:const Text('انضم')),
  ]));
  @override Widget build(BuildContext context){
    final colors=Theme.of(context).colorScheme,game=selected;
    final stat=(widget.user?['gameStatistics'] as List? ?? []).whereType<Map>().where((s)=>s['gameId']==game?.id).firstOrNull;
    final visible=supportedGames.where((g)=>filter=='all'||(filter=='cards'?g.id=='crazy8':g.id!='crazy8')).toList();
    return Column(children:[
      SizedBox(height:58,child:Row(children:[if(game!=null)IconButton(onPressed:back,tooltip:'كل الألعاب',icon:const Icon(Icons.chevron_right,size:30))else const SizedBox(width:18),Expanded(child:Text(game?.name??'الألعاب',style:const TextStyle(fontSize:20,fontWeight:FontWeight.w700))),Padding(padding:const EdgeInsets.symmetric(horizontal:18),child:Text('Plazr',textDirection:TextDirection.ltr,style:TextStyle(color:colors.primary,fontWeight:FontWeight.w700)))])),
      Expanded(child:game==null?ListView(padding:const EdgeInsets.fromLTRB(16,4,16,24),children:[
        Text('اختر لعبتك، وسنبحث لك عن منافس.',style:TextStyle(color:colors.onSurfaceVariant,height:1.5)),const SizedBox(height:18),
        Wrap(spacing:8,children:[for(final entry in {'all':'الكل','boards':'الطاولات','cards':'البطاقات'}.entries)ChoiceChip(label:Text(entry.value),selected:filter==entry.key,onSelected:(_)=>setState(()=>filter=entry.key))]),const SizedBox(height:16),
        LayoutBuilder(builder:(_,constraints)=>GridView.count(crossAxisCount:constraints.maxWidth>=650?4:2,shrinkWrap:true,physics:const NeverScrollableScrollPhysics(),mainAxisSpacing:12,crossAxisSpacing:12,childAspectRatio:.9,children:visible.map(gameCard).toList())),
      ]):ListView(padding:const EdgeInsets.fromLTRB(16,4,16,24),children:[
        Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(borderRadius:BorderRadius.circular(22),gradient:LinearGradient(colors:[game.color,Color.lerp(game.color,Colors.black,.65)!])),child:Row(children:[Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('جاهز للمباراة؟',style:TextStyle(color:Colors.white,fontSize:23,fontWeight:FontWeight.w700)),const SizedBox(height:8),Text(game.description,style:const TextStyle(color:Colors.white70,height:1.5))])),artwork(game,size:110)])),const SizedBox(height:16),
        if(stat!=null)GameRankCard(id:game.id,name:'سجلك في ${game.name}',stat:stat),
        OutlinedButton.icon(onPressed:opening?null:privateMatch,icon:const Icon(Icons.add_circle_outline),label:const Padding(padding:EdgeInsets.symmetric(vertical:14),child:Text('إنشاء مباراة بكود دعوة'))),const SizedBox(height:24),
        const Text('اللعب السريع',style:TextStyle(fontSize:18,fontWeight:FontWeight.w700)),const SizedBox(height:6),Text('نفس مبارياتنا وقواعدنا. انضم إلى لاعب ينتظر، أو انتظره على طاولتك.',style:TextStyle(color:colors.onSurfaceVariant,fontSize:12,height:1.6)),const SizedBox(height:14),
        Material(color:colors.surfaceContainerLow,borderRadius:BorderRadius.circular(18),clipBehavior:Clip.antiAlias,child:Column(children:[for(var i=0;i<game.modes.length;i++)...[if(i>0)const Divider(height:1,indent:16,endIndent:16),modeRow(game,game.modes[i])]])),
      ])),
    ]);
  }
}
