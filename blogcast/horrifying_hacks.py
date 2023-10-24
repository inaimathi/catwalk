import re

LETTER_PRONOUNCIATIONS = {
    "a": "eh",
    "b": "bee",
    "c": "see",
    "d": "dee",
    "f": "eff",
    "g": "jee",
    "h": "ehch",
    "i": "eye",
    "j": "jay",
    "k": "kay",
    "l": "el",
    "m": "em",
    "n": "en",
    "o": "oh",
    "p": "pee",
    "q": "cue",
    "r": "are",
    "s": "ess",
    "t": "tee",
    "u": "you",
    "v": "vee",
    "w": "double you",
    "x": "ecks",
    "y": "why",
    "z": "zee"
}

def _acronym(acronym):
    letters = [LETTER_PRONOUNCIATIONS[lt] for lt in acronym.lower()]
    return " ".join(letters)

MISPRONOUNCED_TOKENS = {
    "chatgpt": "Chat jee pee tee",
    "openai": "open eh eye",
    "strachan": "strohn",
}

ACRONYMS = { "gpt", "ai", "api", "tts", "ssh", "http", "url","amd", "cpu", "tldr", "lts", "ip" }

UNICODE = {
    "🤗": "hugging face"
}

RE = re.compile(r'(?:\b(?:%s|{u"\U0001F600-\U0001F64F"})\b)|(?:%s)' % (
    '|'.join(ACRONYMS.union(MISPRONOUNCED_TOKENS.keys())),
    '|'.join(UNICODE.keys())
), flags=re.IGNORECASE | re.UNICODE)

def _replace(m):
    low = m.group(0).lower()
    if low in ACRONYMS:
        return _acronym(low)
    if low in MISPRONOUNCED_TOKENS:
        return MISPRONOUNCED_TOKENS[low]
    if low in UNICODE:
        return UNICODE[low]
    return m.group(0)

def apply(string):
    return re.subn(RE, _replace, string)[0]
