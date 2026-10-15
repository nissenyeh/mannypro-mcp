"""MCP server exposing 曼報 Pro (pro.manny-li.com) articles."""

from __future__ import annotations

import re
import time

from mcp.server.mcpserver import MCPServer

from .client import CREDENTIALS_FILE, LoginError, MannyProClient, Post

INSTRUCTIONS = """\
曼報 Pro（pro.manny-li.com）文章工具。網站沒有全文搜尋 API。

要找「哪些文章談到某個主題」時，照這四步，不要一次抓全部文章全文：
1. list_all_titles 取得所有文章標題（很輕量）。
2. 依標題語意判斷哪些可能相關，不只比對關鍵字（例如找 FDE，也要想到 Palantir、企業導入 AI、主題文章刊出後幾個月的「你問我答」）。通常挑 10 篇上下。
3. 用 grep_articles 只讀候選文章，搜關鍵字（可用正規表示式涵蓋中英文寫法）。
4. 輸出：真的有談到的文章（附摘錄與網址）、讀了但沒提到的文章，並說明哪些文章只看過標題沒讀內文。結果不夠時再擴大候選。
要讀整篇內容時用 get_article。
"""

mcp = MCPServer("mannypro", instructions=INSTRUCTIONS)
_client: MannyProClient | None = None


def client() -> MannyProClient:
    global _client
    if _client is None:
        _client = MannyProClient()
    return _client


def _post_line(p: Post) -> str:
    tag = f"〔{p.tag}〕" if p.tag else ""
    sub = f"\n  {p.subtitle}" if p.subtitle else ""
    return f"- {p.date} {tag}{p.title}\n  {p.url}{sub}"


@mcp.tool()
def list_tags() -> str:
    """列出曼報 Pro 的文章分類（例如：商業解碼、科技曼讀、巨人之聲、曼報俱樂部）。"""
    return "\n".join(f"- {name}（id: {tag_id}）" for tag_id, name in client().tags().items())


@mcp.tool()
def list_articles(tag: str | None = None, limit: int = 20, cursor: str | None = None,
                  oldest_first: bool = False) -> str:
    """列出曼報 Pro 文章（預設新到舊）。

    Args:
        tag: 分類名稱或 id，例如「巨人之聲」。不給就列全部。
        limit: 這頁要幾篇（1–100）。
        cursor: 上一次回傳的 next_cursor，用來翻下一頁。
        oldest_first: true 時由舊到新。
    """
    posts, next_cursor, total = client().list_posts(
        tag=tag, first=max(1, min(limit, 100)), after=cursor, oldest_first=oldest_first)
    lines = [f"共 {total} 篇，本頁 {len(posts)} 篇："]
    lines += [_post_line(p) for p in posts]
    lines.append(f"\nnext_cursor: {next_cursor}" if next_cursor else "\n（已經是最後一頁）")
    return "\n".join(lines)


@mcp.tool()
def list_all_titles() -> str:
    """一次列出所有文章的日期、分類、標題與 slug（新到舊）。找主題相關文章的第一步：先看標題挑候選。"""
    posts = client().all_posts()
    lines = [f"共 {len(posts)} 篇（日期｜分類｜標題｜slug）："]
    lines += [f"{p.date}｜{p.tag or ''}｜{p.title.strip()}｜{p.path}" for p in posts]
    return "\n".join(lines)


@mcp.tool()
def grep_articles(articles: list[str], pattern: str, context: int = 150, max_snippets: int = 3) -> str:
    """讀指定的幾篇文章全文，找出符合 pattern 的段落（找主題相關文章的第三步）。

    Args:
        articles: 文章 slug、網址或 id 的清單（建議 15 篇以內）。
        pattern: 正規表示式，不分大小寫，例如 "FDE|Forward[- ]Deployed|前線部署"。
        context: 每段摘錄前後各保留幾個字。
        max_snippets: 每篇最多列幾段摘錄。
    """
    try:
        regex = re.compile(pattern, re.I)
    except re.error as e:
        return f"pattern 不是合法的正規表示式：{e}"
    found, missed, failed = [], [], []
    for i, ref in enumerate(articles):
        if i:
            time.sleep(0.5)
        try:
            a = client().fetch_article(ref)
        except (LoginError, ValueError) as e:
            failed.append(f"- {ref}：{e}")
            continue
        hits = [m.start() for m in regex.finditer(a.markdown)]
        if not hits:
            missed.append(f"- {a.title}（{a.url}）")
            continue
        snippets, last = [], -10**9
        for h in hits:
            if h - last < context * 2:
                continue
            last = h
            snippets.append("  …" + a.markdown[max(0, h - context):h + context].replace("\n", " ") + "…")
            if len(snippets) >= max_snippets:
                break
        found.append(f"### {a.title}（{len(hits)} 處）\n{a.url}\n" + "\n".join(snippets))
    out = [f"## 有提到（{len(found)} 篇）", *found, f"\n## 讀了但沒提到（{len(missed)} 篇）", *missed]
    if failed:
        out += [f"\n## 讀取失敗（{len(failed)} 篇）", *failed]
    return "\n".join(out)


@mcp.tool()
def search_articles(keyword: str, limit: int = 20) -> str:
    """用關鍵字比對文章標題、副標、分類與網址 slug（不分大小寫，不搜內文）。

    找主題相關文章時，建議改用 list_all_titles → 挑候選 → grep_articles 的流程，
    因為很多文章標題不會直接寫關鍵字（例如 Visa 系列標題是「過路財神」）。
    """
    kw = keyword.strip().lower()
    hits = [p for p in client().all_posts()
            if kw in p.title.lower() or kw in p.subtitle.lower() or kw in (p.tag or "").lower()
            or kw in (p.slug or "").lower()]
    if not hits:
        return f"找不到標題含「{keyword}」的文章。"
    lines = [f"找到 {len(hits)} 篇" + (f"，顯示前 {limit} 篇" if len(hits) > limit else "") + "："]
    lines += [_post_line(p) for p in hits[:limit]]
    return "\n".join(lines)


@mcp.tool()
def get_article(article: str, include_cover: bool = True) -> str:
    """抓一篇曼報 Pro 文章的全文，回傳 Markdown（需要會員登入，會自動登入）。

    Args:
        article: 文章網址（https://pro.manny-li.com/posts/...）、slug、id，或標題關鍵字。
        include_cover: 是否在開頭附上封面圖。
    """
    try:
        a = client().fetch_article(article)
    except LoginError as e:
        return f"登入失敗：{e}"
    if a.locked:
        return (f"《{a.title}》仍是付費牆畫面，可能帳號沒有會員資格或登入失效。\n{a.url}")
    meta = [f"# {a.title}", "", f"- 原文：{a.url}"]
    if a.date:
        meta.append(f"- 發布日期：{a.date}")
    if a.tag:
        meta.append(f"- 分類：{a.tag}")
    for att in a.attachments:
        meta.append(f"- 附件：{att}")
    if include_cover and a.cover_url:
        meta += ["", f"![封面]({a.cover_url})"]
    return "\n".join(meta) + "\n\n" + (a.markdown or "（沒有抓到正文）")


@mcp.tool()
def login_status() -> str:
    """檢查曼報 Pro 登入狀態；必要時重新登入，並用最新一篇文章確認能讀到全文。"""
    c = client()
    try:
        if not c.has_session():
            email = c.login()
            prefix = f"已用 {email} 重新登入。"
        else:
            prefix = "使用快取的登入 session。"
        latest, _, _ = c.list_posts(first=1)
        a = c.fetch_article(latest[0].url)
    except LoginError as e:
        return f"登入失敗：{e}\n帳密檔：{CREDENTIALS_FILE}"
    if a.locked:
        return f"{prefix}但最新文章仍被付費牆擋住（帳號可能不是會員）。"
    return f"{prefix}可以讀全文：《{a.title}》正文 {len(a.markdown)} 字。"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
