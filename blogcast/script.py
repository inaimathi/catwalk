import json
import os
import re
import urllib

# from basics import caption_image
import markdown
import nltk.data
import requests
import util
from bs4 import BeautifulSoup

_TOK = nltk.data.load("tokenizers/punkt/english.pickle")

def caption_image(src):
    return "TODO - caption this image"

def _sanitize(txt):
    return re.sub("’", "'", re.sub("[\[\]]", "", txt.strip()))

def _flat(list_of_lists):
    return [leaf for child in list_of_lists for leaf in child]

def _element_text(el):
    if isinstance(el, str):
        if el.strip() in {'', '.', '...'}:
            return []
        else:
            return [el]
    elif el.name == "p":
        return _flat([_element_text(c) for c in (el.children)]) + [{"silence": 0.5}]
    elif el.name in {"em", "strong", "i", "b"}:
        return [f" **{_sanitize(el.text)}** "]
    elif el.name == "a":
        return [_sanitize(el.text), " (link in post) "]
    elif el.find("img") not in {None, -1}:
        src = el['src'] or json.loads(el.find("img")["data-attrs"])["src"]
        return ["Here we see an image of:", caption_image(src), {"silence": 0.5}]
    elif el.name in {"h1", "h2", "h3"}:
        return [_sanitize(el.text), {"silence": 1.0}]
    elif el.name == "blockquote":
        ps = el.find_all("p")
        if len(ps) == 1:
            return ["Quote:", _sanitize(el.text), {"silence": 0.5}]
        return ["There is a longer quote:", *[_sanitize(p.text) for p in ps], {"silence": 0.5}, "Now we resume the text.", {"silence": 0.5}]
    elif el.name in {"ul", "ol"}:
        res = []
        for li in el.find_all("li"):
            res.append(_sanitize(li.text))
            res.append({"silence": 0.5})
        res.append({"silence": 0.5})
        return res
    elif el.name == "div" and 'image3' in el['class']:
        ## This is Substacks' stupid image representation
        dat = json.loads(el['data-attrs'])
        return ["Here we see an image of:", caption_image(dat['src']), " The image has been captioned ", dat['title'], ".",  {"silence": 0.5}]
    else:
        print("OTHER", el.name, el.get('class'))
        return [el]

def script_from_soup(soup):
    return [txt for child in soup.children for txt in _element_text(child)]

def script_from_html(html):
    return script_from_soup(BeautifulSoup(html, "html.parser"))

def script_from_markdown(md):
    return script_from_html(markdown.markdown(md))

def script_from_substack(post_url):
    # parsed = urllib.parse.urlparse(post_url)
    # subdomain = parsed.netloc.split(".")[0]
    # slug = [p for p in parsed.path.split("/") if p and p != "p"][0]
    # url = f"https://{subdomain}.substack.com/api/v1/posts/{slug}"
    url = post_url.replace("/p/", "/api/v1/posts/")
    resp = requests.get(url).json()
    return [resp["title"], resp["subtitle"]] + script_from_html(resp["body_html"])

def script_from_langnostic(post_url):
    resp = requests.get(post_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    post = soup.find("div", attrs={"class": "content"}).find_next()
    post.find("div", attrs={"class": "post-nav"}).replaceWith('')
    return script_from_soup(post)

URL_MAP = {
    "^https?://.*?\.substack": script_from_substack,
    "^https?://www.astralcodexten.com": script_from_substack,
    "^https?://(www.)?inaimathi": script_from_langnostic
}

EXTENSION_MAP = {
    ".md": script_from_markdown,
    ".html": script_from_html
}

def _script_from_(thing):
    if thing.startswith("http"):
        # If it's a URL, use the URL scripters
        for pattern, fn in URL_MAP.items():
            if re.match(pattern, thing):
                return fn(thing)
        raise Exception(f"Don't know how to get script from '{thing}'")
    elif os.path.isfile(thing):
        # If it's a thing on disk, use the file scripters
        with open(thing, 'r') as f:
            for ext, fn in EXTENSOIN_MAP:
                if thing.endswith(ext):
                    return fn(f.read())
    else:
        # Otherwise, assume it's an HTML literal
        return script_from_html(thing)

### Script normalization
def _break_paragraphs(script):
    for el in script:
        if isinstance(el, str):
            sentences = _TOK.tokenize(el)
            if len(sentences) == 1:
                yield el
            else:
                for s in sentences:
                    yield s
                    yield {"silence": 0.1}
        elif isinstance(el, dict):
            yield el

def _merge_silence(script):
    "Merges adjacent silences into longer ones. Also implicitly trims off any trailing silence."
    merged = None
    for el in script:
        if isinstance(el, dict) and "silence" in el:
            if merged is None:
                merged = el
            else:
                merged["silence"] = round(merged['silence'] + el['silence'], 1)
        else:
            if merged is None:
                yield el
            else:
                yield merged
                merged = None
                yield el

def _merge_adjacent(script):
    acc = None
    for el in script:
        if isinstance(el, dict):
            if acc is not None:
                yield acc
                acc = None
                yield el
        elif isinstance(el, str):
            if acc is None:
                acc = el
            else:
                acc += el

def normalize_script(script):
    merged = _merge_adjacent(script)
    sentences = _break_paragraphs(merged)
    merged = _merge_silence(sentences)
    return list(merged)

def script_from(target):
    return normalize_script(_script_from_(target))
