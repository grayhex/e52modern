"""Offline validation against the actual installed Gammu codecs; no device I/O."""
import base64
import json
import tempfile
from datetime import datetime
from pathlib import Path

import gammu
import vobject

from symport.phone.personal import PersonalWorkspace, calendar_import

sm = gammu.StateMachine()
assert all(hasattr(sm, name) for name in (
    'GetNextMemory', 'GetNextSMS', 'GetNextCalendar', 'GetNextToDo',
    'GetMemoryStatus', 'GetSMSStatus', 'GetCalendarStatus', 'GetToDoStatus',
    'AddMemory', 'SetMemory', 'AddCalendar', 'SetCalendar', 'AddToDo', 'SetToDo',
    'GetFileSystemStatus', 'SetDebugLevel', 'ReadConfig', 'GetConfig'))
gammu.SetDebugLevel('nothing')
sm.SetDebugLevel('nothing')
records = [
    {'Location': i, 'Type': 'MEETING', 'Entries': [
        {'Type': 'TEXT', 'Value': f'Codec test {i}'},
        {'Type': 'START_DATETIME', 'Value': datetime(2030, 1, i, 9)},
        {'Type': 'END_DATETIME', 'Value': datetime(2030, 1, i, 10)}]}
    for i in (1, 2)]
tasks=[{'Location':1,'Type':'MEMO','Priority':'High','Entries':[{'Type':'TEXT','Value':'Codec task'},{'Type':'END_DATETIME','Value':datetime(2030,1,3,12)}]}]
with tempfile.TemporaryDirectory() as tmp:
    def invoke(config, action, **data):
        assert action == 'read'
        return {'identity': {'fingerprint': 'offline-codec-test', 'write_identity': True}, 'records': records if data['domain']=='calendar' else tasks}
    workspace = PersonalWorkspace(Path(tmp), invoke)
    snapshot = workspace.execute('offline', {'action': 'personal-read', 'domain': 'calendar'})['snapshot']
    exported = workspace.execute('offline', {'action': 'personal-export', 'snapshot': snapshot, 'format': 'ics'})
    raw = base64.b64decode(exported['content']).decode()
    parsed = list(vobject.readComponents(raw))
    assert len(parsed) == 1 and len(parsed[0].vevent_list) == 2
    assert parsed[0].vevent.dtstart.value.tzinfo is None
    rows = calendar_import(raw)
    assert len(rows) == 2 and not any(r['unsupported'] for r in rows)
    plan = workspace.execute('offline', {'action': 'personal-preview', 'snapshot': snapshot, 'rows': rows})
    assert plan['skipped'] == 2 and not plan['changes'] and not plan['conflicts']
    task_snapshot = workspace.execute('offline', {'action':'personal-read','domain':'tasks'})['snapshot']
    task_export = workspace.execute('offline', {'action':'personal-export','snapshot':task_snapshot,'format':'ics'})
    task_rows = calendar_import(base64.b64decode(task_export['content']).decode())
    assert len(task_rows)==1 and not task_rows[0]['unsupported'] and task_rows[0]['priority']=='High'
    task_plan = workspace.execute('offline',{'action':'personal-preview','snapshot':task_snapshot,'rows':task_rows})
    assert task_plan['skipped']==1 and not task_plan['changes'] and not task_plan['conflicts']
    card = gammu.EncodeVCARD({'Location': 0, 'MemoryType': 'ME', 'Entries': [
        {'Type': 'Text_Name', 'Value': 'Codec test'}, {'Type': 'Number_Mobile', 'Value': '12345'}]})
    assert 'BEGIN:VCARD' in card and '12345' in card
print(json.dumps({'gammu': gammu.Version(), 'api': 'available', 'vcard': 'encoded',
                  'icalendar': 'two events, one calendar, floating times, round-trip skipped',
                  'hardware': 'not-tested'}))
