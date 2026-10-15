"""曼報 Pro (pro.manny-li.com) client: Firstory SSO login, article listing and article fetching."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from lxml import html as lxml_html
from markdownify import markdownify

SITE = "https://pro.manny-li.com"
AUTH = "https://open.firstory.fm"
GRAPHQL = "https://prod-api.firstory.me/hosting/v1/graphql"
SHOW_ID = "ckb7oop2y0yit0873vc36njil"
SSO_CLIENT_ID = "firstory.io"

CONFIG_DIR = Path(os.environ.get("MANNYPRO_CONFIG_DIR", Path.home() / ".config" / "mannypro-mcp"))
CREDENTIALS_FILE = CONFIG_DIR / "credentials.env"
COOKIES_FILE = CONFIG_DIR / "cookies.json"
# Full-text cache. Lives in the app-data dir (not ~/.cache) so cache cleaners don't wipe it.
DATA_DIR = Path(os.environ.get("MANNYPRO_DATA_DIR", Path.home() / ".local" / "share" / "mannypro-mcp"))
ARTICLE_CACHE_DIR = DATA_DIR / "articles"
CACHE_MAX_AGE_DAYS = 30
DOWNLOAD_DIR = Path(os.environ.get("MANNYPRO_DOWNLOAD_DIR", Path.home() / "Downloads" / "mannypro-podcast"))

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
)

# Fallback when the posts page can't be parsed.
DEFAULT_TAGS = {
    "cmg4h4b8m009j01v96umu5gj2": "商業解碼",
    "cmh91t7bq006701w40ip94qya": "科技曼讀",
    "cmhcqxd4j00vp01srd4kifbu1": "巨人之聲",
    "cmhw6bb9101l701x0cg8g56vj": "曼報俱樂部",
}

POST_CONNECTION_QUERY = """
query PlayerPostConnection($showId: ID!, $first: Int, $after: String, $postTagId: ID, $orderBy: PostOrderBy) {
  playerPostConnection(showId: $showId, first: $first, after: $after, postTagId: $postTagId, orderBy: $orderBy) {
    edges {
      node {
        id title slug shortId subtitle coverUrl publishedAt createdAt
        postTag { id title }
      }
    }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

EPISODE_CONNECTION_QUERY = """
query PlayerEpisodeConnection($showId: ID!, $after: String) {
  playerEpisodeConnection(showId: $showId, first: 50, after: $after,
                          orderBy: {field: PUBLISHED_AT, direction: DESC}) {
    edges { node { id title publishedAt duration } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

PAYWALL_MARKERS = ("to read member-only articles", "Become a member of")


class LoginError(RuntimeError):
    pass


@dataclass
class Post:
    id: str
    title: str
    slug: str | None
    short_id: str | None
    subtitle: str
    tag: str | None
    created_at: str
    cover_url: str | None

    @property
    def path(self) -> str:
        if self.slug:
            return f"{self.slug}-{self.short_id or self.id}"
        return self.id

    @property
    def url(self) -> str:
        return f"{SITE}/posts/{self.path}"

    @property
    def date(self) -> str:
        return self.created_at[:10]

    @classmethod
    def from_node(cls, node: dict) -> "Post":
        return cls(
            id=node["id"],
            title=node["title"],
            slug=node.get("slug"),
            short_id=node.get("shortId"),
            subtitle=node.get("subtitle") or "",
            tag=(node.get("postTag") or {}).get("title"),
            created_at=node.get("publishedAt") or node.get("createdAt") or "",
            cover_url=node.get("coverUrl"),
        )


@dataclass
class Episode:
    id: str
    title: str
    published_at: str
    duration_sec: int

    @property
    def url(self) -> str:
        return f"{SITE}/episodes/{self.id}"

    @property
    def date(self) -> str:
        return self.published_at[:10]

    @property
    def filename_stem(self) -> str:
        safe = re.sub(r'[\\/:*?"<>|\n]+', " ", self.title).strip()
        return f"{self.date} {safe}"[:150]

    @classmethod
    def from_node(cls, node: dict) -> "Episode":
        return cls(id=node["id"], title=node["title"].strip(), published_at=node.get("publishedAt") or "",
                   duration_sec=int((node.get("duration") or 0) / 1000))


@dataclass
class Article:
    url: str
    title: str
    date: str | None
    cover_url: str | None
    markdown: str
    locked: bool = False
    tag: str | None = None
    attachments: list[str] = field(default_factory=list)
    fetched_at: float = 0.0
    from_cache: bool = False

    @property
    def path(self) -> str:
        return urlparse(self.url).path.rsplit("/", 1)[-1]

    def to_markdown(self, include_cover: bool = True) -> str:
        meta = [f"# {self.title}", "", f"- 原文：{self.url}"]
        if self.date:
            meta.append(f"- 發布日期：{self.date}")
        if self.tag:
            meta.append(f"- 分類：{self.tag}")
        for att in self.attachments:
            meta.append(f"- 附件：{att}")
        if include_cover and self.cover_url:
            meta += ["", f"![封面]({self.cover_url})"]
        return "\n".join(meta) + "\n\n" + (self.markdown or "（沒有抓到正文）")


def _cache_file(path: str) -> Path:
    return ARTICLE_CACHE_DIR / f"{path}.json"


def load_cached(path: str) -> Article | None:
    try:
        data = json.loads(_cache_file(path).read_text())
        return Article(**{**data, "from_cache": True})
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None


def save_cached(article: Article) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    ARTICLE_CACHE_DIR.mkdir(exist_ok=True, mode=0o700)
    data = {k: v for k, v in article.__dict__.items() if k != "from_cache"}
    f = _cache_file(article.path)
    f.write_text(json.dumps(data, ensure_ascii=False))
    f.chmod(0o600)


def cached_paths() -> set[str]:
    if not ARTICLE_CACHE_DIR.exists():
        return set()
    return {f.stem for f in ARTICLE_CACHE_DIR.glob("*.json")}


def _load_credentials() -> tuple[str, str]:
    email = os.environ.get("MANNYPRO_EMAIL")
    password = os.environ.get("MANNYPRO_PASSWORD")
    if (not email or not password) and CREDENTIALS_FILE.exists():
        for line in CREDENTIALS_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if key.strip() == "MANNYPRO_EMAIL":
                email = email or value
            elif key.strip() == "MANNYPRO_PASSWORD":
                password = password or value
    if not email or not password:
        raise LoginError(
            f"找不到帳密。請設定環境變數 MANNYPRO_EMAIL / MANNYPRO_PASSWORD，"
            f"或寫進 {CREDENTIALS_FILE}（兩行 KEY=value）。"
        )
    return email, password


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class MannyProClient:
    def __init__(self) -> None:
        self.http = httpx.Client(
            headers={"user-agent": USER_AGENT, "accept-language": "zh-TW,zh;q=0.9,en;q=0.8"},
            timeout=30,
            follow_redirects=True,
        )
        self._tags: dict[str, str] | None = None
        self._all_posts: tuple[float, list[Post]] | None = None
        self._load_cookies()

    # ---------- cookies ----------

    def _load_cookies(self) -> None:
        if not COOKIES_FILE.exists():
            return
        try:
            for c in json.loads(COOKIES_FILE.read_text()):
                self.http.cookies.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        except (json.JSONDecodeError, KeyError):
            pass

    def _save_cookies(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in self.http.cookies.jar
        ]
        COOKIES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        COOKIES_FILE.chmod(0o600)

    def has_session(self) -> bool:
        return any("manny-li.com" in c.domain for c in self.http.cookies.jar)

    # ---------- login ----------

    def login(self) -> str:
        """Firstory email login → SSO authorize (PKCE) → pro.manny-li.com callback."""
        email, password = _load_credentials()
        self.http.cookies.clear()

        resp = self.http.post(
            f"{AUTH}/api/auth/login/email",
            json={"email": email, "password": password},
            headers={"origin": AUTH, "referer": f"{AUTH}/login", "content-type": "application/json"},
        )
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400 or body.get("status") == "error":
            raise LoginError(f"Firstory 登入失敗：HTTP {resp.status_code} {body.get('error') or resp.text[:200]}")

        verifier, challenge = _pkce_pair()
        state = json.dumps({"next": f"{SITE}/posts"}, separators=(",", ":"))
        params = {
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "client_id": SSO_CLIENT_ID,
            "redirect_uri": f"{SITE}/sso-callback",
            "state": state,
            "sso_confirmed": "1",
        }
        url = f"{AUTH}/auth/sso/authorize?{urlencode(params)}"
        code = None
        for _ in range(10):
            r = self.http.get(url, follow_redirects=False)
            location = r.headers.get("location")
            if not location:
                raise LoginError(f"SSO authorize 沒有導回網站（HTTP {r.status_code}），可能需要在瀏覽器確認授權。")
            url = urljoin(url, location)
            parsed = urlparse(url)
            if parsed.netloc.endswith("manny-li.com") and parsed.path.endswith("/sso-callback"):
                qs = parse_qs(parsed.query)
                code = qs.get("code", [None])[0]
                state = qs.get("state", [state])[0]
                break
            if parsed.path.startswith("/login"):
                raise LoginError("SSO authorize 被導回登入頁：Firstory 登入的 session 沒有生效。")
        if not code:
            raise LoginError("SSO authorize 沒有拿到 code。")

        r = self.http.post(
            f"{SITE}/auth/sso/callback",
            json={"code": code, "state": state, "code_verifier": verifier},
            headers={"origin": SITE, "referer": f"{SITE}/sso-callback"},
        )
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or not body.get("success"):
            raise LoginError(f"網站 SSO callback 失敗：HTTP {r.status_code} {body or r.text[:200]}")

        self._save_cookies()
        return email

    # ---------- listing (public GraphQL) ----------

    def tags(self) -> dict[str, str]:
        if self._tags is None:
            tags: dict[str, str] = {}
            try:
                page = self.http.get(f"{SITE}/posts").text
                for tag_id, name in re.findall(r'href="/posts\?tag=([^"&]+)"[^>]*>([^<]+)<', page):
                    tags[tag_id] = name.strip()
            except httpx.HTTPError:
                pass
            self._tags = tags or dict(DEFAULT_TAGS)
        return self._tags

    def resolve_tag(self, tag: str | None) -> str | None:
        if not tag:
            return None
        tags = self.tags()
        if tag in tags:
            return tag
        for tag_id, name in tags.items():
            if tag.strip() == name or tag.strip() in name:
                return tag_id
        raise ValueError(f"找不到分類「{tag}」。可用分類：{', '.join(tags.values())}")

    def list_posts(self, tag: str | None = None, first: int = 20, after: str | None = None,
                   oldest_first: bool = False) -> tuple[list[Post], str | None, int]:
        variables = {
            "showId": SHOW_ID,
            "first": first,
            "after": after,
            "postTagId": self.resolve_tag(tag),
            "orderBy": {"field": "PUBLISHED_AT", "direction": "ASC" if oldest_first else "DESC"},
        }
        r = self.http.post(GRAPHQL, json={"query": POST_CONNECTION_QUERY, "variables": variables},
                           headers={"origin": SITE})
        r.raise_for_status()
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(payload["errors"][0].get("message"))
        conn = payload["data"]["playerPostConnection"]
        posts = [Post.from_node(e["node"]) for e in conn["edges"]]
        next_cursor = conn["pageInfo"]["endCursor"] if conn["pageInfo"]["hasNextPage"] else None
        return posts, next_cursor, conn.get("totalCount") or len(posts)

    def all_posts(self, max_age: float = 600) -> list[Post]:
        if self._all_posts and time.time() - self._all_posts[0] < max_age:
            return self._all_posts[1]
        posts: list[Post] = []
        cursor = None
        while True:
            batch, cursor, _ = self.list_posts(first=100, after=cursor)
            posts.extend(batch)
            if not cursor:
                break
        self._all_posts = (time.time(), posts)
        return posts

    # ---------- article ----------

    def _article_url(self, ref: str) -> str:
        ref = ref.strip()
        if ref.startswith("http"):
            parsed = urlparse(ref)
            return f"{SITE}{parsed.path}"
        if ref.startswith("/posts/"):
            return f"{SITE}{ref}"
        # Bare id / slug / slug-shortId / title keyword: resolve through the listing.
        for post in self.all_posts():
            if ref in (post.id, post.slug, post.short_id, post.path, post.title):
                return post.url
        matches = [p for p in self.all_posts() if ref.lower() in p.title.lower()]
        if len(matches) == 1:
            return matches[0].url
        if matches:
            titles = "\n".join(f"- {p.title}（{p.url}）" for p in matches[:10])
            raise ValueError(f"「{ref}」對到多篇文章，請指定其中一篇：\n{titles}")
        return f"{SITE}/posts/{ref}"

    def fetch_article(self, ref: str, auto_login: bool = True, use_cache: bool = True,
                      max_age_days: float | None = CACHE_MAX_AGE_DAYS) -> Article:
        """Return an article, from the local full-text cache when it's fresh enough.

        max_age_days=None accepts any cached copy (used for searching).
        """
        url = self._article_url(ref)
        path = urlparse(url).path.rsplit("/", 1)[-1]
        if use_cache:
            cached = load_cached(path)
            if cached and (max_age_days is None or time.time() - cached.fetched_at < max_age_days * 86400):
                return cached
        if auto_login and not self.has_session():
            self.login()
        article = self._fetch_and_parse(url)
        if article.locked and auto_login:
            # Session cookie expired or never worked: log in again once.
            self.login()
            article = self._fetch_and_parse(url)
        if not article.tag:
            # The logged-in page doesn't ship the Post object, so take the tag from the listing.
            post = next((p for p in self.all_posts() if p.path == article.path), None)
            if post:
                article.tag = post.tag
        if not article.locked and article.markdown:
            article.fetched_at = time.time()
            save_cached(article)
        return article

    def _fetch_and_parse(self, url: str) -> Article:
        r = self.http.get(url)
        if r.status_code == 404:
            raise ValueError(f"找不到文章：{url}")
        r.raise_for_status()
        self._save_cookies()
        return parse_article(r.text, str(r.url))

    # ---------- podcast episodes ----------

    def list_episodes(self) -> list[Episode]:
        episodes: list[Episode] = []
        cursor = None
        while True:
            r = self.http.post(GRAPHQL, headers={"origin": SITE}, json={
                "query": EPISODE_CONNECTION_QUERY,
                "variables": {"showId": SHOW_ID, "after": cursor},
            })
            r.raise_for_status()
            payload = r.json()
            if payload.get("errors"):
                raise RuntimeError(payload["errors"][0].get("message"))
            conn = payload["data"]["playerEpisodeConnection"]
            episodes += [Episode.from_node(e["node"]) for e in conn["edges"]]
            if not conn["pageInfo"]["hasNextPage"]:
                return episodes
            cursor = conn["pageInfo"]["endCursor"]

    def resolve_episode(self, ref: str) -> Episode:
        ref = ref.strip()
        m = re.search(r"/episodes/([a-z0-9]+)", ref)
        if m:
            ref = m.group(1)
        episodes = self.list_episodes()
        for ep in episodes:
            if ref in (ep.id, ep.title):
                return ep
        matches = [ep for ep in episodes if ref.lower() in ep.title.lower()]
        if len(matches) == 1:
            return matches[0]
        if matches:
            titles = "\n".join(f"- {ep.title}（id: {ep.id}）" for ep in matches[:10])
            raise ValueError(f"「{ref}」對到多集，請指定其中一集：\n{titles}")
        raise ValueError(f"找不到 Podcast 單集「{ref}」，請先用 list_episodes 查。")

    def episode_audio_url(self, ep: Episode, auto_login: bool = True) -> str:
        """The audio URL is only rendered into the episode page for logged-in members."""
        if auto_login and not self.has_session():
            self.login()
        url = self._audio_url_from_page(ep)
        if not url and auto_login:
            self.login()
            url = self._audio_url_from_page(ep)
        if not url:
            raise LoginError("拿不到音檔網址：帳號可能沒有會員資格，或登入失效。")
        return url

    def _audio_url_from_page(self, ep: Episode) -> str | None:
        r = self.http.get(ep.url)
        r.raise_for_status()
        self._save_cookies()
        m = re.search(r'\\"id\\":\\"' + re.escape(ep.id) + r'\\",.*?\\"audioUrl\\":(null|\\"(.*?)\\")', r.text)
        return m.group(2) if m and m.group(2) else None

    def download_episode(self, ep: Episode, dest_dir: Path | None = None) -> Path:
        dest_dir = dest_dir or DOWNLOAD_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{ep.filename_stem}.mp3"
        if path.exists() and path.stat().st_size > 0:
            return path
        audio_url = self.episode_audio_url(ep)
        tmp = path.with_suffix(".part")
        with self.http.stream("GET", audio_url) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        tmp.rename(path)
        return path


# ---------- HTML parsing ----------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _rsc_post(page: str) -> dict:
    """Pull the Post object out of the Next.js flight payload (fallback for content/metadata)."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', page, re.S)
    flight = "".join(json.loads(f'"{c}"') for c in chunks if c)
    idx = flight.find('"post":{"__typename":"Post"')
    if idx < 0:
        return {}
    start = idx + len('"post":')
    try:
        obj, _ = json.JSONDecoder().raw_decode(flight[start:])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _find_body(doc, h1) -> object | None:
    # The reader column holds: [header (h1, date, cover)] [article body] [hr + further reading].
    container = None
    node = h1
    while node is not None:
        if "max-w-reader" in (node.get("class") or "") and "mx-auto" in (node.get("class") or ""):
            container = node
            break
        node = node.getparent()
    candidates = []
    if container is not None:
        for child in container:
            if not isinstance(child.tag, str) or child.tag == "hr" or h1 in child.iterdescendants():
                continue
            text = _clean(child.text_content())
            if text.startswith("Further Reading"):
                continue
            candidates.append(child)
    candidates += doc.xpath("//div[contains(@class,'[&_h2]') or contains(@class,'prose')]")
    candidates = [c for c in candidates if not any(m in c.text_content() for m in PAYWALL_MARKERS)]
    if not candidates:
        return None
    return max(candidates, key=lambda c: len(_clean(c.text_content())))


def _flatten_figures(fragment_html: str) -> str:
    """<figure><img><figcaption> → image with the caption as alt text, then an italic caption line."""
    root = lxml_html.fragment_fromstring(fragment_html, create_parent="div")
    for fig in root.xpath(".//figure"):
        caption = _clean(" ".join(fig.xpath(".//figcaption//text()")))
        blocks = []
        for img in fig.xpath(".//img[@src]"):
            p = lxml_html.Element("p")
            p.append(lxml_html.Element("img", src=img.get("src"), alt=caption.replace("[", "(").replace("]", ")")))
            blocks.append(p)
        if caption:
            p = lxml_html.Element("p")
            em = lxml_html.Element("em")
            em.text = caption
            p.append(em)
            blocks.append(p)
        if blocks:
            blocks[-1].tail = fig.tail
        fig.getparent().replace(fig, blocks[0]) if blocks else fig.drop_tree()
        for prev, block in zip(blocks, blocks[1:]):
            prev.addnext(block)
    return lxml_html.tostring(root, encoding="unicode")


def html_to_markdown(fragment_html: str) -> str:
    md = markdownify(_flatten_figures(fragment_html), heading_style="ATX", bullets="-",
                     strip=["script", "style", "svg"])
    md = re.sub(r"^(#{1,6} )\*\*(.+?)\*\*[ \t]*$", r"\1\2", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def parse_article(page: str, url: str) -> Article:
    doc = lxml_html.fromstring(page)
    post = _rsc_post(page)

    h1s = doc.xpath("//div[contains(@class,'max-w-reader')]//h1") or doc.xpath("//h1")
    h1 = h1s[0] if h1s else None
    title = post.get("title") or (_clean(h1.text_content()) if h1 is not None else "")

    date = None
    m = re.search(r"發布日期｜(?:<!-- -->)?\s*(\d{4}\.\d{2}\.\d{2})", page)
    if m:
        date = m.group(1)
    elif post.get("publishedAt") or post.get("createdAt"):
        date = (post.get("publishedAt") or post["createdAt"])[:10]

    cover = post.get("coverUrl")
    if not cover:
        imgs = doc.xpath("//img[@alt='Cover']/@src")
        cover = imgs[0] if imgs else None

    tag = (post.get("postTag") or {}).get("title")
    attachments = [a.get("url") or a.get("fileUrl") or json.dumps(a, ensure_ascii=False)
                   for a in post.get("attachments") or [] if isinstance(a, dict)]

    body_md = ""
    body = _find_body(doc, h1) if h1 is not None else None
    if body is not None:
        body_md = html_to_markdown(lxml_html.tostring(body, encoding="unicode"))
    if len(body_md) < 50:
        # Fallback: content shipped as HTML in the flight payload.
        raw = post.get("content") or post.get("contentHtml") or ""
        if isinstance(raw, str) and len(raw) > len(body_md):
            body_md = html_to_markdown(raw)

    # The i18n bundle in <script> always contains the paywall strings, so only check rendered text.
    visible = " ".join(doc.xpath("//body//text()[not(ancestor::script)]"))
    locked = any(m in visible for m in PAYWALL_MARKERS) and len(body_md) < 200
    return Article(url=url, title=title, date=date, cover_url=cover, markdown=body_md,
                   locked=locked, tag=tag, attachments=attachments)
