/// Public room metadata only. Private snapshots/cards never enter this model.
class RetainedTable {
  String roomId='', communityId='', gameId='';
  int seat=-1, capacity=0, ownerSeat=0;
  bool started=false, begun=false, finished=false;
  List<Map<String,dynamic>> roster=[];
  final Set<String> _members={};
  String identity(Map player)=>player['accountId']?.toString().isNotEmpty==true
      ? 'id:${player['accountId']}' : 'seat:${player['seat']}:${player['name']}';
  void clear(){roomId='';communityId='';gameId='';seat=-1;capacity=0;ownerSeat=0;started=false;begun=false;finished=false;roster=[];_members.clear();}
  List<Map<String,dynamic>> apply(Map<String,dynamic> event){
    final assignment={'created','joined','watching'}.contains(event['type']);
    if(!assignment&&event['type']!='room_state'&&event['type']!='begin_match')return [];
    final id=event['roomId']?.toString()??'';
    if(assignment){
      if(id!=roomId)clear();
      roomId=id;communityId=event['communityId']?.toString()??communityId;
      seat=(event['seat'] as num?)?.toInt()??-1;
    }else if(roomId.isEmpty||id.isNotEmpty&&id!=roomId){return [];}
    if(event['settings'] is Map)gameId=event['settings']['gameId']?.toString()??gameId;
    ownerSeat=(event['ownerSeat'] as num?)?.toInt()??ownerSeat;
    capacity=(event['capacity'] as num?)?.toInt()??capacity;
    started=event['started'] is bool?event['started'] as bool:started;
    begun=event['type']=='begin_match'||(event['begun'] is bool?event['begun'] as bool:begun);
    finished=event['finished'] is bool?event['finished'] as bool:finished;
    if(event['roster'] is! List)return [];
    final next=(event['roster'] as List).whereType<Map>().where((p)=>p['name'] is String&&(p['name'] as String).isNotEmpty)
        .map((p)=>Map<String,dynamic>.from(p)).toList();
    final joined=assignment?<Map<String,dynamic>>[]:next.where((p)=>p['seat']!=seat&&!_members.contains(identity(p))).toList();
    // A connected:false update is still the same seated player, not a new join.
    roster=next;_members..clear()..addAll(next.map(identity));
    return joined;
  }
}
