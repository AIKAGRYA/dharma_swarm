import json
from collections import Counter

with open('/tmp/moltbook_research/_cache/lane3/canon_full.json') as f:
    raw = json.load(f)
# raw is a list of {type:"text", text:"..."} entries
text = ''.join(b['text'] for b in raw)
i = text.find('{"success"')
text = text[i:]
data = json.loads(text)

print('keys:', list(data.keys()))
print('count:', len(data['the_great_book']))
sample = data['the_great_book'][0]
print('sample keys:', list(sample.keys()))
print('sample:', sample)

allkeys = set()
for v in data['the_great_book']:
    allkeys.update(v.keys())
print('all keys observed:', allkeys)

print('types:', Counter(v.get('scripture_type') for v in data['the_great_book']).most_common())
print('top authors:', Counter(v.get('prophet_name') for v in data['the_great_book']).most_common(25))
dates = [v.get('canonized_at') for v in data['the_great_book']]
print('first:', min(dates), 'last:', max(dates))

with open('/tmp/moltbook_research/_cache/lane3/canon_clean.json', 'w') as f:
    json.dump(data['the_great_book'], f, indent=2)
print('wrote canon_clean.json with', len(data['the_great_book']), 'verses')
