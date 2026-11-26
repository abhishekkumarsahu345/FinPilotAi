f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"
# Try reading as latin-1 to see the raw bytes around the bullet
with open(f, 'rb') as fh:
    raw = fh.read()

# Find the 'steps' bullet
idx = raw.find(b'steps')
if idx > 0:
    chunk = raw[idx-10:idx+50]
    print("Raw bytes:", chunk)
    print("Hex:", chunk.hex())

# Check BOM
print("BOM (first 4 bytes):", raw[:4].hex())
print("Total bytes:", len(raw))

# Try the bullet character in different encodings
# â€¢ in latin-1 is bytes e2 80 a2 which is UTF-8 for U+2022
print("\nSearching for UTF-8 bullet (e2 80 a2):", b'\xe2\x80\xa2' in raw)
print("Searching for windows-1252 bullet (95):", b'\x95' in raw)
