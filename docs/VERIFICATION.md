# 驗證紀錄（實際跑過什麼、結果、待決定）

> 本檔只記實際執行過的結果。模型：`gpt-4o-mini`；embedding：`text-embedding-3-small`。文件與題目全部虛構。

## 環境
- Python 3.12.10，套件裝在 `demo/.venv`，版本見 `requirements.txt`
- 2026-10-29 使用者同意安裝；`.env` 的 OpenAI key、Slack webhook 由使用者填入，我沒有讀取或印出

## 與 SPEC 的差異（實作時決定）
| 項目 | SPEC | 實際 | 原因 |
|---|---|---|---|
| PDF 載入 | `langchain-community` 的 `PyMuPDFLoader` | 直接用 PyMuPDF 讀頁面，再包成 LangChain `Document` | `langchain-community` 在 import 時發出「停止維護」警告，作品集不該依賴它。已從 requirements 移除並解除安裝，34 個測試照樣通過 |
| 檢索、決策函式的位置 | `app/retrieve.py`、`answer.py` 的 `decide()` | 檢索放在 `app/store.py`，`decide()` 放在 `app/citations.py` | 檢索和 store 共用設定；`decide()` 是純函式，和引用檢查放一起方便測 |
| 啟動伺服器 | `uvicorn app.server:app` | `python scripts/serve.py [--live] [--slack]` | 用 factory 避免 import 時就開 Chroma |
| v1／v2 切換 | 重新產生 v1 | `make_docs.py` 同時把 v1、v2 存進 `knowledge_updates/`，切換時直接複製 | PyMuPDF 每次產生的 PDF hash 都不同，重新產生會讓其他 7 份 PDF 也被判定為「已更新」 |
| 門檻規則 | 用校正題取中點，之後不再調 | 第 2 輪起改成「校正題中有答案的最低分減 0.05」，只用來擋明顯離題的問題 | 見下方第 1 輪檢討 |
| 引用比對 | 正規化後的連續子字串 | 第 2 輪起逐句比對；第 3 版起忽略版面標點（冒號、逗號、表格的 `|`），**文字仍須逐字相符** | 見下方檢討 |
| PDF 表格 | 未指定 | 第 3 版起用 `find_tables()` 辨識表格，每列存成 `cell | cell | cell` | 見下方檢討 |
| 評測輪數 | 最多 2 輪 | 跑了 3 輪 | 第 3 輪超出 SPEC 上限，使用者 2026-10-29 同意後才跑 |

## 文件與陷阱題檢查
- `make_docs.py`：8 份 PDF、8 份 Markdown，以及 returns policy 的 v1、v2
- 陷阱關鍵詞（price match、rent、military、student、retail store、solar、stock、mobile app、gift wrap、guided trip 等）在所有文件中命中 **0** 筆

## 單元測試
- `pytest`：**34 passed**（引用檢查、逐句與標點寬鬆比對、決策表、門檻以下不呼叫模型、manifest 增量、畸形輸出、API 422／降級 200／Slack 失敗仍 200／source 404）

## Mock E2E
- `LLM_MODE=mock`：ingest → A–D 兩種模式 → E → F → collect_results 全部跑完，格式正確。mock 不看分數

## 第 1 輪（live，2026-10-29，log 在 `output/round1/`）
- 校正：K1–K6，有答案的最低 0.633，沒答案的最高 0.370，取中點，`RELEVANCE_MIN=0.50`
- 結果：A+B **4/12**、陷阱題作答 **0/6**、C+D 轉人工 **9/9**
- 檢討（太保守）：
  1. 門檻太高。K1–K6 都是關鍵字很明確的問題，但測試題是口語問法，分數只有 0.31–0.49，A1、A2、A3、A6、B2 還沒進模型就被擋下。另外，陷阱題的分數（0.30–0.59）和有答案的題目重疊，門檻本來就分不開這兩種
  2. A5：模型把同一段的兩句話接成一個引用，中間跳過一句，連續子字串比對沒過
  3. A4、A8：文件明文寫著「不行」或「只寄美加」，模型仍拒答，原因是 prompt 規則寫得太嚴
  4. 每頁的頁首頁尾樣板文字稀釋了 embedding

## 第 2 輪（live，log `20261029-043234-*`）
- 修正：
  - prompt 改成「文件明文寫的『不』可以回答，文件沒提到的不能當成『不』」
  - 引用改成逐句比對
  - 移除頁首頁尾，每段開頭加文件標題，chunk 改成 500／80
  - 校正題加入 K7–K14 共 8 題新的口語題（不碰測試題）
  - 門檻規則改成「有答案的最低分減 0.05」，算出 `RELEVANCE_MIN=0.39`，門檻本身擋掉 4/6 題沒答案的問題
- 結果：A+B **9/12**、陷阱題作答 **0/6**、C+D 轉人工 **9/9**
- 剩下 3 題（A3、B1、B3）都是 `no_valid_citation`，事實正確，但引用格式和原文對不上：
  - B1、B3：PDF 表格被抽成一格一行，模型自己重組成 "Coolers, Glacier 45, 5 years"，或跳過同一格裡的前半段
  - A3：模型在標題後面自己加了冒號

## 第 3 輪（live，log `20261029-044207-*`，作品集以這一輪為準）
- 修正：
  - 表格每列存成一行（`Coolers | Glacier 45 | 5 years`）
  - 引用比對忽略版面標點，但文字仍須逐字相符。新增 4 個測試，包括「7 years 不能過」「跳過同一句裡的字不能過」
  - 重建索引後用同一規則重新校正，`RELEVANCE_MIN` 仍是 **0.39**
- 跑之前：`pytest` 34 passed；ingest unchanged 16
- 結果（程式統計）：
  - A+B **12/12** 答對，且至少一個有效引用指向正確的檔案和頁碼
  - 陷阱題作答 **0/6**
  - C+D 轉人工 **9/9**（3 題被門檻擋下、6 題是模型判定 answerable=false）
  - 12 題作答裡，沒有任何一個引用被檢查擋掉
- Baseline：A+B 事實正確 12/12（不附出處）；C／D 9 題等人工標記，標記表見 `eval/baseline-review_繁中.md`
- 注意：A3、A7、A8 的事實 regex 比較寬（只檢查 no／not／only 這類字），能算通過主要靠「引用必須指向正確頁面」這個條件。三題的實際回答我人工看過，內容都正確：
  - A3："No, fuel canisters cannot be returned for safety and hygiene reasons."
  - A7："No, promo codes cannot be combined with each other."
  - A8："No, we do not ship to any other country."

## E. 文件更新（live，第 3 版索引，`20261029-043534-scenario-update.jsonl`）
- v1：ingest unchanged 16 → 回答「30 days」
- 換成 v2：ingest **updated 1、unchanged 15** → 回答「14 days」，引用 `returns-policy.pdf p.1`
- 已切回 v1（hash 與 `knowledge_updates/returns-policy-v1.pdf` 相同）

## F. AI 服務故障（live，Slack 模式，`20261029-043542-scenario-llm-error.jsonl`）
- `CHAT_MODEL=gpt-does-not-exist` → status `degraded`、reason `llm_error`，API 回 200，Slack **sent**
- 接著用正常模型問 Glacier 45 保固 → answered「5 years」

## 瀏覽器實測（live＋Slack，第 3 版索引）
- `/`：Glacier 45 保固 → 答「5 years」，出處 `warranty.pdf p.2`，引用 "Coolers | Glacier 45 | 5 years"；展開後顯示原文並標出那一列
- `/`：「Halo 能用太陽能板充電嗎」→ 轉人工（model_declined），Slack sent
- 「Talk to a person」→ Slack sent（user_requested）
- `/compare`：price match 題，baseline 回「Cinderpeak Outdoor does not have a price matching policy...」（文件沒這條，是編的）；正式版轉人工，Slack sent
- 手機寬度 375px：版面正常，沒有橫向捲動

## 照實要說的觀察
- **Baseline 在有答案的題目上很準**：兩輪都是 12/12 事實正確（只是沒附出處）。正式版的優勢在陷阱題和轉人工，不在一般題的答對率。作品集不能寫成「baseline 答錯很多」
- Baseline 在陷阱題上常寫「we do not offer X」，聽起來像拒答，其實是**編出一條不存在的政策**。規則判斷會把這種算成「作答」，最後以人工標記為準

- 三輪都是在同一組 21 題上看結果再修正，第 2、3 輪的修正雖然都是通用的（prompt 規則、引用比對、表格處理），但嚴格來說都看過測試題的結果。作品集要寫成「三輪迭代後的結果」，不能把 12/12 說成第一次就達成。要有沒看過的成績，得另外準備一組新題目跑一次

## Baseline 人工標記（使用者，2026-10-29，定案）
- 最終標記：C1–C4 answered、C5–C6 declined；D1 answered、D2 declined、D3 declined
- 與關鍵字規則不一致的題號：C4、D1、D2、D3（以人工為準）
- 過程：第一次標記時 D1 標 declined、D2 標 answered；討論定義後，使用者把 D1 改成 answered（它用退貨規則拒絕了一個照文件應該走保固申請的客戶，還自己補了「凹痕算正常磨損」），D2 改成 declined（它把問題交給客服，沒有下結論）
- C4 判 answered 的理由：文件沒有實體門市，它卻順著客戶的話，講得好像網站上查得到門市
- 結果：baseline 陷阱題作答 **4/6**（C1 比價、C2 租借、C3 軍人折扣、C4 暗示有門市），正式版 **0/6**
- 使用者回饋：標記的感覺像在抓語病。C 題的標準比較明確（文件沒寫，卻講得像有這條規定）；D 題比較主觀

## 作品集素材準備（2026-10-29）
- E、F 用新版 `run_eval.py` 重跑（log 路徑改成相對路徑），結果與之前相同：`20261029-061753-scenario-update.jsonl`、`20261029-061802-scenario-llm-error.jsonl`，Slack sent
- 驗證 README 的說法「新增文件不用重開伺服器」：伺服器運作中切到 v2 並 ingest（updated 1），透過伺服器的 `/ask` 問，回答「14 days」。之後已切回 v1 並 ingest
- widget 新增 `?expand=1`（自動展開第一個出處，截圖用），展開後自動捲到被標記的那一行
- 截圖用 `portfolio/src/shoot_demo.py`，對 live 伺服器截圖，裁切範圍寫在腳本裡。截圖裡的回答是當次的 live 輸出：baseline 那次回「we do not offer price matching for the Ember 2 Camp Stove...」，用詞和評測 log 不同，但都是在編造規定
- `collect_results.py --summary` 的輸出原樣用在 board 04

## 講解影片（2026-10-29）
- 語音：HeyGen voice `28J6z3XNsqyMvvCqxUiK`，speed 0.9。OAuth 免費額度已用完（"0 seconds of free voice-generation time left"），依 DESIGN §9 改用 `_portfolio-design-system/.env` 的 API key（`make-voice.sh --api`），8 段都用同一個 voice 產生。key 沒有印出，也沒有寫進任何檔案
- 8 個場景，89.48 秒；BGM 用共用曲目、音量 0.12
- `hyperframes check`：16:9 和 9:16 都是 0 errors、0 warnings
- render：`video/help-docs-support-assistant-16x9.mp4`（1920×1080、89.5 s）、`video-reel/help-docs-support-assistant-9x16.mp4`（1080×1920、89.5 s）
- 抽畫格檢查了 10 個時間點，包括第 0 格、各場景、結尾卡和 flow 的圈選：第 0 格不是空白；16:9 沒有浮水印；9:16 的浮水印在安全點跳位；字幕沒有壓到 board
- **聲音沒有人耳聽過**：音量平衡、發音（LangChain、Chroma、Cinderpeak）要由使用者實際聽一次

## 對照表的決定（使用者，2026-10-29）
- `collect_results.py` 的 before／after 對照表只留兩列：「有答案的題目答對」12/12 對 12/12、「陷阱題被拿去作答」4/6 對 0/6
- 拿掉「C+D 轉人工」那一列。原因有二：baseline 本來就沒有轉人工功能，這一列沒什麼可比；D 題的判斷又太主觀。D 題的結果照樣列在逐題明細裡（正式版 3/3 轉人工）
- D3 討論時提到的設計（先查訂單存不存在，再決定是照實際狀態回覆還是轉客服）需要接上訂單系統。這個 demo 沒有接，提案只能寫成「可以加」

## 待決定
- 無
