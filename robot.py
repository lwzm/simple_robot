#!/usr/bin/env python3

"""
robot.py
"""


import datetime
import json
import functools
import logging
import os
import re
import signal
import sys
import time
import urllib.parse

import bs4
import redis
import requests

# https://urllib3.readthedocs.io/en/latest/advanced-usage.html#ssl-warnings
requests.packages.urllib3.disable_warnings()

HTML_PARSER = "html5lib"
HTML_PARSER = "html.parser"
HTML_PARSER = "lxml"

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 6.2; WOW64)"

upstream = "http://localhost:1112"
proxies = {
    "http": "socks5://localhost",
    "https": "socks5://localhost",
}


def get_meta_tag_content(soup: bs4.BeautifulSoup, name: str) -> str or None:
    """从 BeautifulSoup 对象中提取出指定名字的 meta 标签的内容

    keywords or Keywords or KEYWORDS
    description or Description or DESCRIPTION

    >>> soup = bs4.BeautifulSoup('''
    ... <meta name="Keywords" content="k1,k2" />
    ... <meta name="Description" content="NB!" />
    ... ''', 'html.parser')
    >>> get_meta_tag_content(soup, "keywords")
    'k1,k2'
    """

    assert name == name.lower(), name

    for name in [name, name.capitalize(), name.upper()]:
        tag = soup.select_one("meta[name={}]".format(name))
        if tag:
            return tag.get("content")


def do_it(task):
    url = "http://{}".format(task)
    page = {}

    try:
        resp = session.get(url, timeout=10, verify=False)
    except Exception:
        page["proxy"] = True
        resp = session.get(url, timeout=20, verify=False, proxies=proxies)

    parsed = urllib.parse.urlparse(resp.url)
    abs_url = functools.partial(urllib.parse.urljoin, resp.url)

    page["url"] = resp.url
    page["path"] = parsed.path
    page["netloc"] = parsed.netloc
    page["scheme"] = parsed.scheme
    page["code"] = resp.status_code

    if resp.status_code >= 300:
        return

    markup = resp.content
    if resp.encoding != 'ISO-8859-1':
        try:
            markup = markup.decode(encoding=resp.encoding)
        except (LookupError, UnicodeDecodeError):  # unknown encoding or decode error
            pass

    soup = bs4.BeautifulSoup(markup, HTML_PARSER)

    page["encoding"] = soup.original_encoding or resp.encoding
    page["title"] = soup.title and soup.title.text.strip()
    page["keywords"] = get_meta_tag_content(soup, "keywords")
    page["description"] = get_meta_tag_content(soup, "description")

    for tag in soup.find_all(["script", "style"]):
        tag.clear()

    page["text"] = "\n".join(filter(None, map(
        str.strip, soup.text.split("\n")
    )))

    images = set()
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        # how to prevent `data:image/jpeg;base64,...` ?
        if not src or len(src) > 256:
            continue
        src = abs_url(src)
        if src.startswith("http"):
            # fucking http:/a/b/c.jpg
            x = urllib.parse.urlparse(src)
            if x.scheme and x.netloc and not x.query:
                images.add(src)

    page["images"] = images
    return page


def child_do(task):
    info = do_it(task)

    if not info:
        sys.exit(1)

    data = json.dumps(info, default=list, ensure_ascii=False, indent=4,
                      separators=(",", ": "), sort_keys=True).encode()

    url_fmt = (upstream + "/data/{}").format
    session.put(url_fmt(task), data=data)
    if info["netloc"] != task:
        session.put(url_fmt(info["netloc"]), data=data)

    sys.exit()


def main(task=None):
    if task:
        return print(do_it(task))

    def _sig_term(signum, frame):
        nonlocal flag_loop
        flag_loop = False

    def _sig_alrm(signum, frame):
        os.kill(pid, signal.SIGTERM)

    signal.signal(signal.SIGALRM, _sig_alrm)
    signal.signal(signal.SIGTERM, _sig_term)

    flag_loop = True

    while flag_loop:
        task = session.get(upstream + "/queue")
        if task.status_code == 200:
            task = task.text
        if not task:
            continue

        pid = os.fork()

        if pid:
            t = time.time()
            signal.alarm(240)  # wait 4 minutes
            _, exit_code = os.wait()
            time_cost = "{:.2f}".format(time.time() - t)
            print(task, time_cost, exit_code, sep="\t", flush=True)
            signal.alarm(0)
        else:
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            child_do(task)


if __name__ == "__main__":
    main(*sys.argv[1:])
