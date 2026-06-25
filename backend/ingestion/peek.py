import os

MAILDIR = "data/raw/maildir"  
'''
 it takes this path as relative to from where you are running this file. so, set it accordingly
 as i am running it from the root directory so i have set it this.
'''

# Count total emails
total = 0
for root, dirs, files in os.walk(MAILDIR):
    total += len([f for f in files if not f.startswith(".")])

print(f"Total emails found: {total:,}")

# Show first 5 paths
count = 0
for root, dirs, files in os.walk(MAILDIR):
    for f in files:
        if not f.startswith("."):
            print(os.path.join(root, f))
            count += 1
        if count >= 5:
            break
    if count >= 5:
        break