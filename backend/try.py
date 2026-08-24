# remember these files has to be deleted at then end


import json

total = 0

with open("../data/processed/resolved_claims.jsonl") as f:
    for line in f:
        data = json.loads(line)

        claim_type = data.get("claim_type")
        subject = str(data.get("subject_name", "")).lower()
        obj = str(data.get("object_name", "")).lower()
        id = str(data.get("claim_id"))

        if claim_type == "reports_to" and ("Kean" in subject):# or "kean" in obj):
            print(id)
            total += 1

print(f"Total matching rows: {total}")
        