import re

MISPRONOUNCED_TOKENS = {
    "chatgpt": "Chat jee pee tee",
    "tts": "tee tee ess",
    "openai": "open ai eye",
    "api": "ai pee eye",
    "gpt-4": "jee pee tee four",
    "gpt-3": "jee pee tee three",
    "strachan": "strohn"
}

UNICODE = {
    "🤗": "hugging face"
}

RE = re.compile(r'(?:\b(?:%s|{u"\U0001F600-\U0001F64F"})\b)|(?:%s)' % (
    '|'.join(MISPRONOUNCED_TOKENS.keys()),
    '|'.join(UNICODE.keys())
), flags=re.IGNORECASE | re.UNICODE)

def _replace(m):
    low = m.group(0).lower()
    return MISPRONOUNCED_TOKENS.get(low, UNICODE.get(low, m.group(0)))

def apply(string):
    return re.subn(RE, _replace, string)[0]
