import json
lines = open('/tmp/moltbook_research/03b_canon_corpus.jsonl').readlines()
verses = [json.loads(l) for l in lines]
phrase = "join the Congregation. My shell is new"
matched = 0
matched_short = 0
joining_words_total = 0
joining_words_template = 0
for v in verses:
    text = v.get('text', '') or ''
    cat = v.get('category', '')
    if cat == 'joining_words':
        joining_words_total += 1
        if phrase in text:
            joining_words_template += 1
    if phrase in text:
        matched += 1
        if len(text) < 250:
            matched_short += 1
print(f'Verses with template phrase anywhere: {matched}')
print(f'  of which short (<250 chars): {matched_short}')
print(f'joining_words category total: {joining_words_total}')
print(f'  of which match template: {joining_words_template}')
print(f'  joining_words NOT matching template (original content): {joining_words_total - joining_words_template}')
