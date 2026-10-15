"""MCP server exposing 曼報 Pro (pro.manny-li.com) articles."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .client import CREDENTIALS_FILE, LoginError, MannyProClient, Post

mcp = MCPServer("mannypro")
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
def search_articles(keyword: str, limit: int = 20) -> str:
    """用關鍵字搜尋文章標題、副標與分類（不分大小寫），回傳符合的文章清單。"""
    kw = keyword.strip().lower()
    hits = [p for p in client().all_posts()
            if kw in p.title.lower() or kw in p.subtitle.lower() or kw in (p.tag or "").lower()]
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
