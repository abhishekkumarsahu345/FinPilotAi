f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"
with open(f, encoding='utf-8-sig') as fh:
    content = fh.read()

# Check the specific characters near the bullet
idx = content.find("step_count} steps")
if idx >= 0:
    chunk = content[idx:idx+80]
    print("Found at", idx)
    print(repr(chunk))
else:
    print("Not found")

# Check the View Steps arrow
idx2 = content.find("View Steps")
if idx2 >= 0:
    chunk2 = content[idx2:idx2+20]
    print(repr(chunk2))
