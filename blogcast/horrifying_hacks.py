import re

MISPRONOUNCED_TOKENS = {
    "chatgpt": "Chat jee pee tee",
    "tts": "tee tee ess",
    "openai": "open ai eye",
    "api": "ai pee eye",
    "🤗": "hugging face"
}

RE = re.compile(r'%s|{u"\U0001F600-\U0001F64F"}' % '|'.join(MISPRONOUNCED_TOKENS.keys()), flags=re.IGNORECASE | re.UNICODE)

def hack_string(string):
    replace = lambda m: MISPRONOUNCED_TOKENS.get(m.group(0).lower(), m.group(0))
    return re.subn(RE, replace, string)[0]
