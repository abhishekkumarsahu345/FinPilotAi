f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"
with open(f, encoding='utf-8-sig') as fh:
    content = fh.read()

checks = ['canManage', 'handleToggle', 'handleShowArchiveConfirm', 'handleArchive', 'handleSetDefault', 'archiveConfirm', 'toggleConfirm']
for c in checks:
    count = content.count(c)
    print(f"{c}: {count} occurrences")
