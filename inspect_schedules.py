f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"
with open(f, encoding='utf-8') as fh:
    content = fh.read()
idx = content.find("view === 'schedules' && (")
if idx >= 0:
    snippet = content[idx:idx+4000]
    print(repr(snippet))
