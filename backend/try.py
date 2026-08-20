# remember these files has to be deleted at then end

import json
reply_count = 0
ref_count = 0
total = 0
with open('../data/processed/parsed_emails.jsonl') as f:
    for line in f:
        email = json.loads(line)
        total += 1
        if email.get('in_reply_to'):
            reply_count += 1
        if email.get('references') and len(email['references']) > 0:
            ref_count += 1
print(f'Total emails:              {total}')
print(f'With In-Reply-To header:   {reply_count}')
print(f'With References header:    {ref_count}')