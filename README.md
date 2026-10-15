# mannypro-mcp

讓 Claude Code、Codex 等 AI agent 直接讀《曼報 Pro》（[pro.manny-li.com](https://pro.manny-li.com)）會員文章的 MCP server。

可以列文章、依分類篩選、搜尋標題，並把整篇文章（含小標、連結、圖表與圖說）轉成 Markdown；也能下載會員 Podcast，在你的電腦上免費轉成逐字稿。

> [!IMPORTANT]
> **⚠️ 你需要自己有《曼報 Pro》的付費會員帳號才能讀全文。**
>
> 這個工具只是用**你自己的帳號**登入後代為讀取，不會繞過付費牆，也不附帶任何帳號。
>
> **請只供個人閱讀、整理筆記使用，不要轉載或散布付費內容。**
>
> 👉 還不是會員？**[訂閱《曼報 Pro》](https://pro.manny-li.com/join)**，支持作者持續產出深度內容。

## 👀 使用範例

裝好之後，直接用中文問 Claude Code / Codex 就可以。

**範例一：讀一篇文章並解釋**——「幫我看 Visa 商業解碼最後一篇，並且解釋他們怎麼算 ROIC」

AI 會自己找到 Visa 系列（標題叫「過路財神」）的最後一篇，讀完全文和文中圖表，再把 ROIC 的算法拆給你看：

<img src="docs/images/example-visa-roic.png" alt="在 Claude Code 問 Visa 商業解碼最後一篇怎麼算 ROIC 的範例" width="720">

（截圖中原文付費圖表的數字已模糊處理。）

**範例二：找出談到某個主題的文章**——「幫我搜尋曼報 pro 中可能提到 FDE 的文章」

AI 先看完 122 篇標題，挑出 25 篇可能相關的去讀內文，最後回報 3 篇真的有談到 FDE（附重點與連結），也列出讀了但沒提到的 22 篇：

<img src="docs/images/example-fde-search.png" alt="在 Claude Code 搜尋曼報中提到 FDE 的文章的範例" width="720">

（截圖中會員交流活動的會員發言已模糊處理。）

---

## 📌 第 0 步：先準備好你的曼報 Pro 帳密（必做）

這個工具**不附帶任何帳號**，要用你自己的《曼報 Pro》會員帳號登入，而且只支援「**Email＋密碼**」登入。不管你等一下是交給 AI 安裝還是自己手動裝，都要先準備好這組帳密。

- **已經用 Email＋密碼登入曼報 Pro 的人**：記下這組帳密，直接看下一段。
- **平常用 Google / Apple / Facebook 登入的人**：你的帳號預設**沒有密碼**，請照下面 3 個步驟先設一組（大約 1 分鐘）：

1. 登入 [pro.manny-li.com](https://pro.manny-li.com)，點右上角頭像 →「**會員管理**」

   <img src="docs/images/step1-member-menu.png" alt="點右上角頭像，選會員管理" width="520">

2. 在「帳戶資訊」頁點「**會員中心**」連結（信箱、密碼、第三方綁定都在 Firstory 會員中心管理）

   <img src="docs/images/step2-member-center.png" alt="帳戶資訊頁點會員中心" width="640">

3. 在 Firstory 的「帳戶資訊」頁，「**密碼**」欄位按「**修改**」設定密碼

   <img src="docs/images/step3-set-password.png" alt="Firstory 帳戶資訊的密碼欄位，按修改" width="640">

   - **Email** 就是這一頁上方 Email 欄位顯示的信箱
   - 設好密碼後 Google 等綁定帳號照常能用，不需要解除綁定
   - 可以到 [open.firstory.fm/login](https://open.firstory.fm/login) 用「Email＋密碼」登入一次，確認這組帳密可用

---

## 🔒 你的帳密存在哪裡？安全嗎？

**一句話：帳密只存在你自己的電腦裡，只會拿去登入 Firstory 官方網站，不會上傳到 GitHub，也不會傳給其他人。**

| 存什麼 | 存在哪裡 | 誰讀得到 |
|---|---|---|
| Email＋密碼 | 你電腦裡的 `~/.config/mannypro-mcp/credentials.env`<br>（Mac 的完整路徑是 `/Users/你的使用者名稱/.config/mannypro-mcp/credentials.env`） | 只有你電腦上的你這個帳號（檔案權限設成 600） |
| 登入後的通行證（cookie） | 同一個資料夾的 `cookies.json` | 同上，權限 600 |

- **密碼只會送到一個地方：** Firstory 官方登入網址 `https://open.firstory.fm`（就是你平常登入曼報 Pro 的那一頁）。程式碼是公開的，可以在 [`client.py`](src/mannypro_mcp/client.py) 的 `login()` 看到這是唯一用到密碼的地方。
- **不會進 GitHub：** 帳密檔放在你的家目錄，不在這個 repo 資料夾裡，`git push` 也推不上去。
- **不會寫進 Claude Code / Codex 的設定檔：** 照預設的「帳密檔」方式安裝，AI 工具的設定裡只有啟動指令，沒有帳密。
- **想在 Finder 找到它：** 按 `⌘ + Shift + G`，貼上 `~/.config/mannypro-mcp`，按 Enter。這是隱藏資料夾，平常不會看到。
- **想刪掉：** 刪除整個 `~/.config/mannypro-mcp` 資料夾就好（或跟 AI 說「幫我刪除曼報 MCP 的帳密」）。刪掉之後這個工具就讀不到全文了。

**有兩點要老實跟你說：**

1. **帳密檔是一般文字檔，沒有加密。** 權限設定能擋住電腦上的其他使用者，但擋不住「用你的帳號登入電腦的人」。所以建議幫 Firstory **設一組沒在別的地方用過的密碼**，就算外洩也不會影響你的其他帳號。
2. **如果你把密碼直接打在對話裡給 AI，** 這段對話會經過 AI 服務商（Anthropic 或 OpenAI）。不想這樣的話，請 AI「建好帳密檔就好，我自己填」，再用文字編輯器打開那個檔案自己填（在終端機輸入 `open -e ~/.config/mannypro-mcp/credentials.env`）。

---

## 🚀 最簡單的安裝方式：交給 AI 幫你裝（不用懂程式）

如果你已經有 [Claude Code](https://claude.com/claude-code) 或 [Codex](https://developers.openai.com/codex)，不用自己打任何指令，請 AI 照這份說明幫你裝好。

**開始前：** 確認你已經完成上面的「第 0 步」，手邊有曼報 Pro 的 Email＋密碼，等一下 AI 會問你。

**接著三步：**

1. 打開終端機（Mac：按 `⌘ + 空白鍵`，輸入「終端機」或「Terminal」後按 Enter），輸入 `claude` 按 Enter 開啟 Claude Code（用 Codex 的人輸入 `codex`）。

2. 把下面這段**整段複製**，貼進去按 Enter：

   ```text
   幫我安裝這個 MCP server：https://github.com/nissenyeh/mannypro-mcp
   請把 repo clone 到 ~/mannypro-mcp，讀 README，照最後面「給 AI agent 的安裝步驟」一步一步做完。
   需要我的曼報 Pro 帳密時再問我；裝好後幫我測試能不能讀到全文。
   ```

3. 過程中 AI 會：
   - 請你允許它執行指令 → 選「Yes」或「允許」
   - 問你曼報 Pro 的 **Email 和密碼** → 直接回覆它
   - 最後回報「可以讀全文」就代表成功了

**裝好之後：** 把 Claude Code / Codex 關掉重開（輸入 `/exit` 再重新輸入 `claude`），就可以直接用中文叫它讀曼報，例如：

- 「列出曼報最新 10 篇文章」
- 「抓曼報〈名利雙收 I〉全文，整理成重點筆記」

> 🔒 帳密只會存在你自己的電腦，詳見上面的「[你的帳密存在哪裡？安全嗎？](#-你的帳密存在哪裡安全嗎)」。不想把密碼打給 AI 的話，可以請它「建好帳密檔就好，我自己填」。

想自己一步步手動安裝的人，請看下面的完整說明。

---

## 工具

| 工具 | 用途 | 需要登入 |
|---|---|---|
| `list_tags` | 列分類（商業解碼、科技曼讀、巨人之聲、曼報俱樂部） | 否 |
| `list_articles(tag, limit, cursor, oldest_first)` | 列文章，可依分類篩選、翻頁 | 否 |
| `list_all_titles` | 一次列出全部文章的日期、分類、標題、slug | 否 |
| `search_articles(keyword)` | 用關鍵字比對標題／副標／分類／網址（不搜內文） | 否 |
| `grep_articles(articles, pattern)` | 只讀指定幾篇的全文，列出符合關鍵字的段落 | 是（自動） |
| `get_article(article)` | 抓全文轉 Markdown；`article` 可以是網址、slug 或標題關鍵字 | 是（自動登入） |
| `list_episodes` | 列出會員 Podcast 全部集數 | 否 |
| `download_episode(episode)` | 下載一集 Podcast 的 mp3 到本機 | 是（自動） |
| `transcribe_episode(episode)` | 在你的電腦上把一集 Podcast 轉成逐字稿（免費、不需要 API key） | 是（自動） |
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

### 1-3 寫入你的帳密（必做）

先確認你已經照最上面的「[第 0 步](#-第-0-步先準備好你的曼報-pro-帳密必做)」準備好 Email＋密碼，再把它存到電腦上：

兩種方式擇一：

**方式 A：帳密檔（推薦）**——帳密只存在你自己的電腦，不會出現在 agent 的設定檔裡。

```bash
mkdir -p ~/.config/mannypro-mcp
chmod 700 ~/.config/mannypro-mcp
cat > ~/.config/mannypro-mcp/credentials.env <<'EOF'
MANNYPRO_EMAIL=you@example.com
MANNYPRO_PASSWORD=你的密碼
EOF
chmod 600 ~/.config/mannypro-mcp/credentials.env
```

**方式 B：環境變數**——在下面註冊 MCP 時用 `MANNYPRO_EMAIL`、`MANNYPRO_PASSWORD` 帶進去（範例見各 agent 的說明）。

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
- 「幫我看 Visa 商業解碼最後一篇，並且解釋他們怎麼算 ROIC」
- 「曼報 Podcast 有哪些集？把 Stripe 那集轉成逐字稿」

### 會員 Podcast：下載與轉逐字稿

跟 AI 說「把曼報 Podcast 的 Stripe 那集轉成逐字稿」就可以，它會依序：

1. 用你的會員帳號登入，下載那集的 mp3
2. **在你自己的電腦上**用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 轉成繁體中文逐字稿（每 30 秒一段、附時間標記）
3. 轉好後讀逐字稿，幫你整理重點

要知道的事：

- **免費、不需要申請任何 API key**，音檔也不會上傳到別的服務。
- **第一次用會先下載語音模型**（預設 `small`，約 500 MB），之後就不用再下載。
- **需要一點時間**：一般電腦大約是音檔長度的一半（實測 17 分鐘的一集花了 8 分鐘），Apple M 系列晶片通常更快。轉錄在背景跑，AI 會隔一段時間回來看進度，你可以先做別的事。
- **是自動轉錄，會有少量錯字**（例如同音字）。想要更準可以跟 AI 說「用 large-v3-turbo 模型轉」，會更慢一些。
- 檔案存在 `~/Downloads/mannypro-podcast/`（mp3 和逐字稿 `.md` 放在一起），可以用環境變數 `MANNYPRO_DOWNLOAD_DIR` 改位置。
- 音檔和逐字稿一樣是付費內容，**請只供個人使用，不要分享出去**。

### 找「哪些文章談到某個主題」

網站沒有全文搜尋 API，而且很多文章標題不會直接寫關鍵字（例如 Visa 系列叫「過路財神」）。所以 server 內建的使用說明會請 AI 照這個流程做，不會一次把全部文章抓下來：

1. `list_all_titles` 拉全部標題
2. 依標題判斷哪些可能相關（例如找 FDE，也會想到 Palantir、企業導入 AI 的文章）
3. `grep_articles` 只讀這幾篇候選文章的全文，找關鍵字
4. 回報：真的有談到的文章＋摘錄、讀了但沒提到的、哪些只看過標題

實際畫面請看最上面的「[使用範例](#-使用範例)」。

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
| 其他 `Firstory 登入失敗：…` | 多半是密碼錯；用 Google 等社群帳號登入的人要先照最上面「第 0 步」設密碼 |
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

---

## 給 AI agent 的安裝步驟

> 這一段是寫給 Claude Code / Codex 等 AI agent 看的：使用者請你安裝時，依序執行，每一步確認成功再進下一步。使用者多半不熟指令，請用白話跟他說明進度。

1. **確認 uv**：執行 `uv --version`。沒有的話執行 `curl -LsSf https://astral.sh/uv/install.sh | sh`，然後用 `~/.local/bin/uv` 或重新載入 shell 後的 `uv`。
2. **取得程式**：若 `~/mannypro-mcp` 不存在，`git clone https://github.com/nissenyeh/mannypro-mcp.git ~/mannypro-mcp`；已存在就 `git -C ~/mannypro-mcp pull`。接著 `uv --directory ~/mannypro-mcp sync`。
3. **帳密**：
   - 問使用者曼報 Pro（Firstory）的登入 Email 與密碼。如果他說平常用 Google 等社群帳號登入、沒有密碼，請他照 README 最上面「第 0 步」的截圖先設定密碼。
   - 寫入 `~/.config/mannypro-mcp/credentials.env`（內容兩行：`MANNYPRO_EMAIL=...`、`MANNYPRO_PASSWORD=...`），資料夾權限 700、檔案權限 600。
   - 如果使用者想自己填，就建立兩個值留空的檔案，告訴他檔案路徑，等他說填好再繼續。
   - 不要把帳密寫進 repo、MCP 設定檔或任何其他地方。
4. **測試登入**：執行
   `uv --directory ~/mannypro-mcp run python -c "from mannypro_mcp.server import login_status; print(login_status())"`
   - 看到「可以讀全文」才算成功。
   - 失敗時對照 README 的「疑難排解」，用白話告訴使用者該怎麼修（例如密碼打錯、帳號沒有會員資格）。
5. **註冊 MCP**（用絕對路徑，`~` 先展開成實際家目錄）：
   - Claude Code：`claude mcp add --scope user mannypro -- uv --directory <家目錄>/mannypro-mcp run mannypro-mcp`，再用 `claude mcp list` 確認 `mannypro` 顯示 Connected。
   - Codex：`codex mcp add mannypro -- uv --directory <家目錄>/mannypro-mcp run mannypro-mcp`，再用 `codex mcp list` 確認。
   - 如果 `uv` 不在 PATH（例如剛安裝），command 改用 uv 的絕對路徑（`which uv` 或 `~/.local/bin/uv`）。
6. **告訴使用者**：已經裝好；需要**關掉並重新開啟** Claude Code / Codex 才會出現 mannypro 工具；附上兩三句可以直接說的範例（如「列出曼報最新 10 篇文章」）。
