import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/retained_table.dart';

void main(){
  test('notify only genuinely new seats; reconnect and metadata do not duplicate joins',(){
    final table=RetainedTable();
    final me={'seat':0,'accountId':'owner_test_1234','name':'أنا','connected':true};
    final other={'seat':1,'accountId':'other_test_1234','name':'صديقي','connected':true};
    Map<String,dynamic> room(String type,List<Map<String,Object>> roster)=>{'type':type,'roomId':'ABCDEF','seat':0,'communityId':'majlis','capacity':2,'settings':{'gameId':'pool'},'roster':roster};
    expect(table.apply(room('created',[me])),isEmpty);
    expect(table.apply(room('room_state',[me,other])).single['name'],'صديقي');
    expect(table.apply(room('room_state',[me,other])),isEmpty);
    expect(table.apply(room('room_state',[me,{...other,'connected':false}])),isEmpty);
    expect(table.apply(room('room_state',[me,other])),isEmpty);
    expect(table.apply(room('joined',[me,other])),isEmpty);
    expect(table.apply({...room('room_state',[me]),'roomId':'UNRELATED'}),isEmpty);
    expect(table.roster.length,2);expect(table.communityId,'majlis');expect(table.gameId,'pool');
    table.apply(room('room_state',[me]));expect(table.apply(room('room_state',[me,other])).length,1);
    table.apply({'type':'room_state','roomId':'ABCDEF','ownerSeat':1});expect(table.ownerSeat,1);
    table.apply({'type':'begin_match','roomId':'ABCDEF'});expect(table.begun,isTrue);
    table.clear();expect(table.roomId,isEmpty);expect(table.roster,isEmpty);expect(table.begun,isFalse);
  });
  test('watchers get a baseline roster without notification spam',(){
    final table=RetainedTable();
    expect(table.apply({'type':'watching','roomId':'AAAAAA','seat':-1,'roster':[{'seat':0,'accountId':'owner','name':'الأول'}]}),isEmpty);
    expect(table.apply({'type':'room_state','roomId':'AAAAAA','roster':[{'seat':0,'accountId':'owner','name':'الأول'},null]}),isEmpty);
  });
}
