# 實作規格：只照自家文件回答的客服助理（RAG，Python＋LangChain）

> 方向與理由見 `../../00-作品集方向_繁中.md`；本檔是**可直接執行的規格**。遇到本檔沒寫到、或跟實際 API 不符的地方：在 `docs/VERIFICATION.md` 的「待決定」記下來，選最小的改動保住原意，不擴大範圍。
> 程式碼、註解、README、commit message 用英文；`docs/VERIFICATION.md` 用繁體中文。

---

## 0. 前置條件（使用者完成，見 `../../01-帳號準備步驟_繁中.md`）
- `demo/.env` 已填：`OPENAI_API_KEY`、`SLACK_WEBHOOK_URL`。
- 使用者已同意在 `demo/.venv` 安裝 §1.1 的套件。
- 缺值時只做離線部分（`LLM_MODE=mock`、單元測試），並在 VERIFICATION.md 記下哪些沒測。

## 1. 硬性規則
1. **套件**：只裝 `requirements.txt` 列的套件，裝在 `demo/.venv`，版本鎖定（`==`）。不裝全域套件。
   - `langchain-core`、`langchain-text-splitters`、`langchain-community`（`PyMuPDFLoader`）、`langchain-openai`、`langchain-chroma`、`chromadb`、`pymupdf`、`openai`、`python-dotenv`、`fastapi`、`uvicorn`、`httpx`、`pytest`
2. **機密**：不印、不寫進 log，也不寫進任何會進 git 的檔案。錯誤訊息裡的 key、webhook URL 一律換成 `***`。
3. **不 git push**、不建 GitHub repo，由使用者決定。本機 commit 可以。
4. **OpenAI 用量**：開發一律 `LLM_MODE=mock`（`DeterministicFakeEmbedding`＋假的 chat 回覆）。真的呼叫只在 §8.3 E2E，評測整批最多跑 2 輪；每次 live 執行前在對話裡說一聲。
5. **虛構資料**：品牌、產品、政策全部虛構，每份文件頁首或檔頭標 `Fictional demo content`。不使用真實品牌名稱或真實業主文件。
6. **數字由程式算**：結果表、題數、通過率一律由 `collect_results.py` 從 run log 統計，不讓 LLM 產生任何統計數字。

## 2. 檔案結構（最終）
```
demo/
  README.md  requirements.txt  .env.example  .gitignore
  docs/  SPEC.md  SETUP.md  OPERATIONS.md  VERIFICATION.md
  knowledge/            # 虛構品牌文件（live 索引來源）
  knowledge_updates/    # returns-policy v2（E 題用，替換 knowledge/ 裡的 v1）
  scripts/
    make_docs.py        # 用 PyMuPDF 產生 PDF（含表格）＋寫 Markdown
    ingest.py           # CLI：增量建索引；--rebuild 清空重建
    ask.py              # CLI：問一題；--mode grounded|baseline
    run_eval.py         # 跑 eval/questions.json；--mode grounded|baseline|both；--only A1,C3
    collect_results.py  # run log → output/results.md（對照表）
    swap_returns_policy.py  # E 題：v1↔v2 切換
  app/
    config.py           # 讀 .env、預設值、遮罩機密
    ingest.py           # 載入、切段、chunk id、manifest（sha256）增量
    retrieve.py         # Chroma 檢索＋relevance 分數
    citations.py        # 引用驗證（純函式）
    answer.py           # grounded chain：門檻 → structured output → 引用驗證 → 決策
    baseline.py         # naive chain
    handoff.py          # Slack 通知（或 SLACK_MODE=log 寫 jsonl）
    server.py           # FastAPI
    static/  index.html  compare.html  widget.css  widget.js
  eval/  questions.json  calibration.json
  tests/ test_citations.py  test_decision.py  test_ingest_manifest.py  test_schema.py  test_server.py
  output/  run-log/  results.md  handoff-log.jsonl   # 不進 git（保留 .gitkeep）
```

## 3. 虛構品牌與文件
品牌：**Cinderpeak Outdoor (demo)**，賣露營爐、營燈、保冷箱、睡袋、行動電源，只出貨美國與加拿大。

| 檔案 | 格式 | 內容重點（測試題會用到） |
|---|---|---|
| returns-policy.pdf（v1） | PDF 2 頁 | 30 天退貨、未使用、退款 5–7 個工作天、燃料罐不可退 |
| knowledge_updates/returns-policy.pdf（v2） | PDF 2 頁 | 改成 **14 天**，其餘不變；頁首寫 v2 生效日 |
| warranty.pdf | PDF 3 頁，**含表格** | 各產品線保固年限（爐 3 年、營燈 2 年、保冷箱 5 年、睡袋 1 年、行動電源 1 年）、不保範圍、申請步驟 |
| shipping-rates.pdf | PDF 2 頁，**含表格** | 美國／加拿大運費級距、免運門檻（US$75）、出貨時間 |
| manual-ember-2-stove.pdf 等產品手冊 ×5 | PDF 各 2–4 頁 | 規格、使用、清潔、常見故障排除 |
| faq.md | MD | 帳號、付款方式、訂單追蹤 |
| order-changes.md | MD | 下單後 1 小時內可改、取消流程 |
| gift-cards-and-promos.md | MD | 禮物卡不過期、折扣碼不可疊加 |
| care-and-storage.md | MD | 保養與收納 |
| international-shipping.md | MD | 只寄美加，其他國家不寄 |
| spare-parts.md | MD | 可買的零件清單（不含價格） |

共 16 份。**陷阱題的答案絕不能出現在任何文件裡**；`make_docs.py` 寫完後跑一次 grep 確認 C 類關鍵詞（例如 price match、rental、military、store location）不在文件中，結果記進 VERIFICATION.md。

## 4. Ingest（`app/ingest.py`）
- PDF：`PyMuPDFLoader`，每頁一個 Document，metadata 保留 `source`（相對檔名）與 `page`（1 起算）。MD：讀全文，`page=None`，以標題切節（`MarkdownHeaderTextSplitter`），metadata 加 `section`。
- 切段：`RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)`。
- **chunk id**：`{source}#p{page}#c{idx}`（MD 用 `#s{section_slug}#c{idx}`），決定性，重跑相同。
- **manifest**：`output/index-manifest.json` 記 `{source: sha256}`。新增或改動的檔案先刪掉該 source 的舊 chunk 再加；manifest 有、磁碟沒有的 → 刪除。未改動的不碰。CLI 印出 `added / updated / removed / unchanged` 數量。
- Embedding：`OpenAIEmbeddings(model=EMBED_MODEL)`，預設 `text-embedding-3-small`；mock 模式用 `DeterministicFakeEmbedding(size=256)`，Chroma 目錄依模式分開（`output/chroma-live`、`output/chroma-mock`）。

## 5. 回答流程
### 5.1 檢索（`app/retrieve.py`）
`similarity_search_with_relevance_scores(question, k=TOP_K)`，`TOP_K` 預設 5。回傳 `[{chunk_id, source, page, text, score}]`。

### 5.2 Grounded（`app/answer.py`）
1. 最高分 `< RELEVANCE_MIN` → **不呼叫 LLM**，`status=handoff`、`reason=low_relevance`。
2. 呼叫 chat model（`CHAT_MODEL`，`temperature=0`），`with_structured_output` 取得：
   ```json
   {"answerable": true, "answer": "...", "citations": [{"chunk_id": "...", "quote": "..."}]}
   ```
   Prompt 規則（`app/prompts/grounded.md`）：只能用提供的段落；段落沒有明確答案就 `answerable=false`；每個事實都要有 citation；quote 必須是段落原文的連續片段，最長 200 字元。
3. **引用驗證**（`app/citations.py`，純函式）：
   - `chunk_id` 必須在這次檢索結果裡；
   - `quote` 正規化（小寫、合併空白、統一引號與破折號）後必須是該段落正規化文字的子字串；
   - 長度 ≥ 12 字元（防止只引 "the" 這種）。
4. 決策（純函式 `decide()`）：
   | 條件 | status | reason |
   |---|---|---|
   | `answerable=false` | handoff | model_declined |
   | `answerable=true`，但 0 個有效引用 | handoff | no_valid_citation |
   | `answerable=true`，部分引用無效 | answered | —（只顯示有效引用，log 記下無效的） |
   | `answerable=true`，全部有效 | answered | — |
5. `status=handoff` 時回固定訊息：「I couldn't find this in our help documents, so I've passed your question to our support team.」並呼叫 `handoff.notify()`。
6. **錯誤**：OpenAI 例外（`APIError`、`APIConnectionError`、`RateLimitError`、`NotFoundError`、timeout 20 秒）重試 1 次；仍失敗 → `status=degraded`、`reason=llm_error`，回固定訊息「Our assistant is having trouble right now. Your question has been sent to our support team.」＋告警。**API 回 200，不丟 500**。

### 5.3 Baseline（`app/baseline.py`）
同一份索引、同樣 `TOP_K`；prompt 只有「You are a helpful support assistant for Cinderpeak Outdoor. Use the context below to answer the customer's question.」＋段落＋問題；純文字輸出；無門檻、無 structured output、無引用驗證、無 handoff。README 與作品集都要寫明這是**自己寫的簡化版**，用來對照。

### 5.4 轉人工（`app/handoff.py`）
- Slack Incoming Webhook，訊息含：問題、reason、前 3 個檢索段落（`source p.N`＋前 160 字元）、時間、`request_id`。
- `SLACK_MODE=log`（mock 預設）時只寫 `output/handoff-log.jsonl`。
- Slack 失敗不能讓 `/ask` 失敗：記 log，回應照常。

## 6. API 與網頁（`app/server.py`）
| Method | Path | 說明 |
|---|---|---|
| POST | `/ask` | `{question, mode: "grounded"\|"baseline"}` → `{request_id, status, answer, citations:[{chunk_id, source, page, quote}], reason}`；question 空白或 > 1000 字元回 422 |
| POST | `/handoff` | `{question, note?}`，使用者按「Talk to a person」→ Slack，`reason=user_requested` |
| GET | `/source/{chunk_id}` | 回該段原文與 metadata，供「展開出處」 |
| GET | `/health` | 索引 chunk 數、模式（不含機密） |
| GET | `/` | `index.html`：客服 widget 風格（右下角泡泡展開），答案下列出處、可展開原文、Talk to a person 按鈕、頁尾標 demo／虛構 |
| GET | `/compare` | `compare.html`：同一題左右並排（baseline vs grounded），錄影用 |

前端只用原生 HTML/CSS/JS，不用 CDN。

## 7. 評測
### 7.1 題目（`eval/questions.json`）
```json
{"id": "A1", "category": "A", "question": "...",
 "expect": {"status": "answered", "facts": ["30 days"], "sources": [{"source": "returns-policy.pdf", "page": 1}]},
 "note": "..."}
```
| 類別 | 題數 | 判定（程式） |
|---|---|---|
| A 文件有答案 | 8 | status=answered、`facts` 全部以不分大小寫 regex 命中、至少 1 個有效引用指向 `sources` 之一（page 為 null 時只比 source） |
| B 表格／精確數字 | 4 | 同上，facts 用精確數字 regex（例如 `\$75`、`\b5[- ]year`） |
| C 陷阱題 | 6 | grounded：status=handoff；baseline：見 7.2 |
| D 模糊需真人 | 3 | status=handoff（例如「我的爐子壞了可以換新的嗎」沒給購買日期與故障描述 → 算轉人工即可；若 answered 但引用有效，記為「answered（可接受）」另列，不算失敗也不算通過，寫進 VERIFICATION） |
| E 文件更新 | 1 | 先在 v1 問（預期 30 天）→ `swap_returns_policy.py v2` → `ingest.py` → 再問（預期 14 天、引用 v2 頁面）；ingest 輸出必須是 `updated 1`、其餘 unchanged |
| F 模型錯誤 | 1 | 以 `CHAT_MODEL=gpt-does-not-exist` 跑一題 → status=degraded、handoff-log 或 Slack 有一筆 `llm_error`；接著用正常模型問下一題成功 |

### 7.2 Baseline 在 C 類的判定
Baseline 是自由文字，先用規則判斷：命中拒答 regex（`don't have|do not have|no information|not (mentioned|specified|covered|included)|couldn't find|can't find|unable to (find|confirm)|contact (our )?support`）→ 記「拒答」，否則記「作答（亂編）」。**另外由使用者逐題人工確認一次**，人工標記寫進 `eval/baseline-labels.json`；結果表以人工標記為準，並列出規則與人工不一致的題號。

### 7.3 門檻校正
`RELEVANCE_MIN` 只用 `eval/calibration.json`（6 題，3 題有答案、3 題陷阱，**不與 questions.json 重複**）校正一次，結果與選定值寫進 VERIFICATION.md。之後跑正式評測不再調。

### 7.4 輸出
- `run_eval.py` 每題寫一行到 `output/run-log/<timestamp>-<mode>.jsonl`：問題、status、reason、answer、citations（含是否有效）、檢索分數、耗時、模型名稱。
- `collect_results.py` 產生 `output/results.md`：
  - 對照表：baseline vs grounded 的「答對且出處正確（A+B）」「陷阱題作答（C）」「正確轉人工（C+D）」
  - 逐題明細
  - 頁首註明：題目與文件都是虛構、題數、模型名稱、執行日期

## 8. 測試
### 8.1 單元測試（`pytest`，mock，不連網）
- `test_citations.py`：子字串、正規化（大小寫、空白、彎引號）、chunk_id 不在檢索結果、太短的 quote
- `test_decision.py`：§5.2 決策表每一列；低於門檻時 chat model 不被呼叫（用假物件計數）
- `test_ingest_manifest.py`：新增、改動、刪除、未改動四種情況的計數與 chunk 刪加
- `test_schema.py`：structured output 缺欄位、型別錯 → 視為 no_valid_citation，不丟例外
- `test_server.py`：`/ask` 422、degraded 回 200、`/handoff` 在 Slack 失敗時仍 200、`/source` 404

### 8.2 Mock E2E
`LLM_MODE=mock`：`ingest.py --rebuild` → `run_eval.py --mode both` 能跑完、檔案格式正確（不看分數）。

### 8.3 Live E2E（使用者同意後）
1. `ingest.py --rebuild`（live embedding）
2. 校正 `RELEVANCE_MIN`（§7.3）
3. `run_eval.py --mode both` → `collect_results.py`
4. E、F 題
5. 瀏覽器實際操作 `/` 與 `/compare`：展開出處、Talk to a person → Slack 收到

## 9. 文件
- `README.md`（英文）：這是什麼、架構圖、如何跑、結果表連結、限制（虛構資料、baseline 是自寫簡化版、沒做的功能）
- `docs/SETUP.md`：venv、`.env`、ingest、啟動伺服器
- `docs/OPERATIONS.md`：加文件／換文件 → `ingest.py`；調 `RELEVANCE_MIN`、`TOP_K`；看 handoff log；換模型
- `docs/VERIFICATION.md`（繁中）：每一步實際跑過什麼、結果、待決定事項
