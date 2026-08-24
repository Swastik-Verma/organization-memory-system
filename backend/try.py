# remember these files has to be deleted at then end



import json
res_map = json.loads(open('../data/processed/resolution_map.json').read())
dup_ids = set(json.loads(open('../data/processed/duplicate_ids.json').read()))

null_made_by = 0
unresolvable = 0
total = 0
with open('../data/processed/extractions_final.jsonl') as f:
    for line in f:
        ext = json.loads(line)
        if ext['message_id'] in dup_ids:
            continue
        for dec in ext.get('decisions', []):
            desc = dec.get('description','').strip()
            if not desc:
                continue
            total += 1
            mb = dec.get('made_by')
            if not mb or not mb.strip():
                null_made_by += 1
            elif mb.strip() not in res_map:
                unresolvable += 1
print(f'Total decisions: {total}')
print(f'Null made_by: {null_made_by}')
print(f'Unresolvable made_by: {unresolvable}')
print(f'Should have MADE_BY edge: {total - null_made_by - unresolvable}')
