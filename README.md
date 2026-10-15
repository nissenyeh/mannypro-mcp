# mannypro-mcp

讓 Claude Code、Codex 等 AI agent 直接讀《曼報 Pro》（[pro.manny-li.com](https://pro.manny-li.com)）會員文章的 MCP server。

可以列文章、依分類篩選、搜尋標題，並把整篇文章（含小標、連結、圖表與圖說）轉成 Markdown。

> ⚠️ 你需要自己有《曼報 Pro》的付費會員帳號才能讀全文，這個工具只是用你的帳號登入後代為讀取。請只供個人閱讀、整理筆記使用，不要轉載或散布付費內容。

## 工具

| 工具 | 用途 | 需要登入 |
|---|---|---|
| `list_tags` | 列分類（商業解碼、科技曼讀、巨人之聲、曼報俱樂部） | 否 |
| `list_articles(tag, limit, cursor, oldest_first)` | 列文章，可依分類篩選、翻頁 | 否 |
| `search_articles(keyword)` | 用關鍵字搜標題／副標／分類 | 否 |
| `get_article(article)` | 抓全文轉 Markdown；`article` 可以是網址、slug 或標題關鍵字 | 是（自動登入） |
| `login_status` | 檢查帳密能不能登入、能不能讀到全文 | 是 |

---

## 1. 前置作業

### 1-1 安裝 uv

這個 server 用 Python 寫，透過 [uv](https://docs.astral.sh/uv/) 執行，套件會自動安裝。

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或 macOS：brew install uv
```

### 1-2 下載這個 repo

```bash
git clone https://github.com/nissenyeh/mannypro-mcp.git ~/mannypro-mcp
cd ~/mannypro-mcp
uv sync
```

後面的設定會用到這個資料夾的**絕對路徑**，用 `pwd` 查一下，例如 `/Users/you/mannypro-mcp`。

### 1-3 設定你自己的帳密（必做）

這個 MCP server **不附帶任何帳號**，一定要填你自己的《曼報 Pro》登入帳密（就是在 [open.firstory.fm](https://open.firstory.fm/login) 用 Email 登入的那組），沒設定的話只能列文章、讀不到全文。

兩種方式擇一：

**方式 A：帳密檔（推薦）**——帳密只存在你自己的電腦，不會出現在 agent 的設定檔裡。

```bash
mkdir -p ~/.config/mannypro-mcp
cat > ~/.config/mannypro-mcp/credentials.env <<'EOF'
MANNYPRO_EMAIL=you@example.com
MANNYPRO_PASSWORD=你的密碼
EOF
chmod 600 ~/.config/mannypro-mcp/credentials.env
```

**方式 B：環境變數**——在下面註冊 MCP 時用 `MANNYPRO_EMAIL`、`MANNYPRO_PASSWORD` 帶進去（範例見各 agent 的說明）。

> 只支援 Email＋密碼登入。如果你平常是用 Google / Apple / Facebook 登入 Firstory，請先到 Firstory 帳號設定裡設一組密碼。

登入成功後，session cookie 會存在 `~/.config/mannypro-mcp/cookies.json`（權限 600），過期時會自動用帳密重新登入。

先在終端機測一下帳密對不對：

```bash
uv --directory ~/mannypro-mcp run python -c \
  "from mannypro_mcp.server import login_status; print(login_status())"
# 成功會看到：已用 you@example.com 重新登入。可以讀全文：《…》正文 xxxx 字。
```

---

## 2. 在 Claude Code 使用

用 `claude mcp add` 註冊（把路徑換成你的）：

```bash
# 用帳密檔（方式 A）
claude mcp add --scope user mannypro -- \
  uv --directory /Users/you/mannypro-mcp run mannypro-mcp

# 或用環境變數（方式 B）
claude mcp add --scope user mannypro \
  -e MANNYPRO_EMAIL=you@example.com -e MANNYPRO_PASSWORD=你的密碼 -- \
  uv --directory /Users/you/mannypro-mcp run mannypro-mcp
```

- `--scope user`：所有專案都能用；拿掉就只在目前專案生效。
- 確認狀態：`claude mcp list` 應該看到 `mannypro: ... ✔ Connected`。
- 要**開新的 Claude Code session** 工具才會出現；在 session 裡輸入 `/mcp` 可以看到 `mannypro` 和它的工具。

---

## 3. 在 Codex 使用

用 `codex mcp add` 註冊：

```bash
# 用帳密檔（方式 A）
codex mcp add mannypro -- uv --directory /Users/you/mannypro-mcp run mannypro-mcp

# 或用環境變數（方式 B）
codex mcp add mannypro \
  --env MANNYPRO_EMAIL=you@example.com --env MANNYPRO_PASSWORD=你的密碼 -- \
  uv --directory /Users/you/mannypro-mcp run mannypro-mcp
```

或直接編輯 `~/.codex/config.toml`：

```toml
[mcp_servers.mannypro]
command = "uv"
args = ["--directory", "/Users/you/mannypro-mcp", "run", "mannypro-mcp"]
# 用方式 B 才需要下面這行
# env = { MANNYPRO_EMAIL = "you@example.com", MANNYPRO_PASSWORD = "你的密碼" }
```

- 確認狀態：`codex mcp list`。
- 重新開 Codex（CLI 或 IDE 擴充）後，在對話裡輸入 `/mcp` 可以看到 `mannypro`。

---

## 4. 怎麼用

直接用自然語言跟 agent 說，例如：

- 「列出曼報最新 10 篇文章」
- 「曼報有哪些分類？列出巨人之聲最近 5 篇」
- 「搜尋曼報講 Stripe 的文章」
- 「抓曼報〈名利雙收 I〉全文，整理成重點筆記」
- 「把商業解碼『因貨得福』系列 I–IV 全部抓下來，合成一份 Markdown」

`get_article` 回傳的格式：

```markdown
# 名利雙收 I：別人出錢出力的高利潤生意

- 原文：https://pro.manny-li.com/posts/...
- 發布日期：2026.09.25
- 分類：商業解碼

![封面](https://image.firstory-cdn.me/...)

...正文...

![圖 1：Springer Nature 各業務營收結構（FY2023-FY2025）。](https://i.urusai.cc/y9wBZ.png)

*圖 1：Springer Nature 各業務營收結構（FY2023-FY2025）。*

## 收稿：研究者主動送上門的稿源
...
```

圖片保留原始網址，沒有下載到本機。

---

## 疑難排解

| 狀況 | 原因／解法 |
|---|---|
| `找不到帳密` | 沒做 1-3；檢查 `~/.config/mannypro-mcp/credentials.env` 或環境變數 |
| `Firstory 登入失敗：user_not_found` | Email 打錯，或這個 Email 沒有 Firstory 帳號 |
| 其他 `Firstory 登入失敗：…` | 多半是密碼錯；用社群帳號登入的人要先設密碼 |
| `仍是付費牆畫面` | 帳號登入成功但沒有《曼報 Pro》會員資格（或會員已過期） |
| 想強制重新登入 | 刪掉 `~/.config/mannypro-mcp/cookies.json` |
| agent 裡看不到工具 | 註冊後要開新 session；`claude mcp list` / `codex mcp list` 看是否 Connected |

---

## 運作原理

1. `POST open.firstory.fm/api/auth/login/email` 用帳密取得 Firstory session
2. `GET open.firstory.fm/auth/sso/authorize`（PKCE S256，client_id `firstory.io`）→ 導回 `pro.manny-li.com/sso-callback?code=…`
3. `POST pro.manny-li.com/auth/sso/callback {code, state, code_verifier}` → 取得網站 session cookie
4. 文章列表走公開的 `prod-api.firstory.me/hosting/v1/graphql`（`playerPostConnection`）
5. 全文從登入後的文章頁 HTML 解析，用 [markdownify](https://github.com/matthewwithanm/python-markdownify) 轉成 Markdown

網站改版時解析可能會壞，歡迎開 issue。
