# remember these files has to be deleted at then end

import json
from src.parsing.noise_detector import detect_noise_regions

with open('../data/processed/extraction_subset.jsonl') as f:
    lines = f.readlines()

total = 0
has_noise = 0
noise_type_counts = {'quoted_reply': 0, 'forward_header': 0, 'signature': 0}

for line in lines[:500]:  # check first 500 emails
    email = json.loads(line)
    regions = detect_noise_regions(email.get('body', ''))
    total += 1
    if regions:
        has_noise += 1
        for r in regions:
            noise_type_counts[r.region_type] += 1

print(f'Checked: {total} emails')
print(f'With noise detected: {has_noise} ({has_noise/total*100:.1f}%)')
print(f'Quoted replies found: {noise_type_counts["quoted_reply"]}')
print(f'Forward headers found: {noise_type_counts["forward_header"]}')
print(f'Signatures found: {noise_type_counts["signature"]}')