import json
import os
import re
import time
import urllib

import markdown
import nltk.data
import requests
import util
from basics import caption_image, summarize_code
from bs4 import BeautifulSoup

import blogcast.horrifying_hacks as hax

try:
    _TOK = nltk.data.load("tokenizers/punkt/english.pickle")
except LookupError:
    nltk.download("punkt")
    _TOK = nltk.data.load("tokenizers/punkt/english.pickle")

def _subs(sub_map, string):
    res = string
    for pattern, replacement in sub_map.items():
        res = re.sub(pattern, replacement, res)
    return res

def _sanitize(txt):
    return _subs({
        "’": "'",
        "[\[\]`]": "",
        "-": " "
    }, txt.strip())

def _flat(list_of_lists):
    return [leaf for child in list_of_lists for leaf in child]

def _element_text(el):
    if isinstance(el, str):
        if el.strip() in {'', '.', '...'}:
            return []
        else:
            return [_sanitize(el)]
    elif 'posted' in el.get('class', []):
        try:
            parsed = time.strptime(el.text, "%a %b %d, %Y")
            date = time.strftime("%A, %B %d, %Y", parsed)
            return [f"Posted on {date}", {"silence": 0.5}]
        except Exception:
            return []
    elif el.name == "p":
        return _flat([_element_text(c) for c in (el.children)]) + [{"silence": 0.5}]
    elif el.name in {"em", "strong", "i", "b"}:
        return [_sanitize(el.text)]
    elif el.name == "a":
        return [_sanitize(el.text), " (link in post) "]
    elif el.find("img") not in {None, -1}:
        print(f"IMG = {el}")
        src = el['src'] or json.loads(el.find("img")["data-attrs"])["src"]
        return ["Here we see an image of:", _sanitize(caption_image(src)), {"silence": 0.5}]
    elif el.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
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
    elif el.name in {"code", "pre"}:
        if 5 >= len(el.text.split()):
            return [_sanitize(el.text)]
        else:
            return ["Here is a code block.", {"silence": 0.5}, _sanitize(summarize_code(el.text)), "That's the end of the code block.", {"silence": 0.5}]
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
    url = post_url.replace("/p/", "/api/v1/posts/")
    resp = requests.get(url).json()
    return [resp["title"], resp["subtitle"]] + script_from_html(resp["body_html"])

def script_from_tlp(post_url):
    resp = requests.get(post_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    post = soup.find("div", attrs={"id": "content"})
    for trash in soup.findAll(re.compile("script|iframe|form")):
        trash.replaceWith('')

    for trash in soup.find(attrs={"id": "share"}):
        trash.replaceWith('')

    title = post.find("h1").text
    posted = f"Posted on {soup.find(attrs={'class': 'dated'}).text.strip()}"
    return [title, posted] + script_from_soup(post.find(attrs={"id": "text"}))

def script_from_slatestar(post_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site'
    }
    resp = requests.get(post_url, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser")
    post = soup.findAll(attrs={"class": re.compile("pjgm-post(title|meta|content)")})
    return [res[0].text, " ".join([el.text for el in res[1].findAll("span")[0:2]])] + script_from_soup(res[2])



def script_from_langnostic(post_url):
    resp = requests.get(post_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    post = soup.find("div", attrs={"class": "content"}).find_next()
    post.find("div", attrs={"class": "post-nav"}).replaceWith('')

    ## FIXME - figure out how to represent footnotes properly in audio
    footnote_container = post.find(attrs={"class": "footnotes"})
    if footnote_container is None:
        return script_from_soup(post)

    footnotes = footnote_container.findAll("li")
    footnote_count = len(footnotes)
    foot_note = f"This post had {footnote_count} {'footnotes that were' if footnote_count > 1 else 'footnote that was'} ommitted from this recording for now."
    for footnote in footnotes:
        ref_id = footnote.findAll("a")[-1].get("href").lstrip("#")
        post.find("a", {"id": ref_id}).replaceWith('')
    footnote_container.replaceWith('')

    return script_from_soup(post) + [{"silence": 0.5}, foot_note]

URL_MAP = {
    "^https?://.*?\.substack": script_from_substack,
    "^https?://www.astralcodexten.com": script_from_substack,
    "^https://slatestarcodex": script_from_slatestar,
    "^https?://(www.)?inaimathi": script_from_langnostic,
    "^https?://thelastpsychiatrist.com": script_from_tlp
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
                acc = acc.rstrip() + " " + el.lstrip()
    if acc is not None:
        yield acc
        acc = None

def normalize_script(script):
    merged = _merge_adjacent(script)
    hacked = [hax.apply(s) if isinstance(s, str) else s for s in merged]
    sentences = _break_paragraphs(hacked)
    return list(_merge_silence(sentences))

def script_from(target):
    return normalize_script(_script_from_(target))
