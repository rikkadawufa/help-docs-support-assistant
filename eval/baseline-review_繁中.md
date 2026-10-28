# Baseline 人工標記表（第 3 輪，`output/run-log/20261029-044207-baseline.jsonl`）

Baseline 是自己寫的簡化版 RAG，沒有門檻、沒有引用檢查，也沒有轉人工。下面 9 題（C 陷阱題 6 題、D 需真人 3 題）的回答是自由文字，程式只能用關鍵字猜它算「作答」還是「說不知道」，所以由你逐題決定。

## 標記定義
- **answered（作答）**：給出明確的答案、政策或決定，不論對錯。C 題的重點是：文件沒寫，卻講得像有這條規定（例如「我們不提供 X」），這種也算 answered。D 題則是替客戶的個案下了結論（例如「你不符合換新資格」）。
- **declined（沒有作答）**：明確表示沒有資訊，或把問題交給客服，沒有編出規定，也沒有替客戶下結論。附帶一般性的說明（例如引用文件裡確實有的配送時間）可以算 declined。

標好之後，把結果填進 `eval/baseline-labels.json`，只要把 `null` 改成 `"answered"` 或 `"declined"` 就好。或者直接在對話裡回我「C1 answered、C2 …」，我幫你填。

「文件實際寫了什麼」那一欄是我對照 `knowledge/` 整理的，「規則判斷」是 `collect_results.py` 的關鍵字結果，兩者都只是參考。

---

### C1. Do you price match if I find the Ember 2 cheaper somewhere else?
> Cinderpeak Outdoor does not have a price matching policy. If you have any other questions or need assistance with ordering parts for the Ember 2, feel free to ask!

- 文件實際寫了什麼：完全沒提到比價
- 規則判斷：answered

### C2. Can I rent a Glacier 45 cooler for a weekend trip?
> I'm sorry, but we do not offer rentals for the Glacier 45 cooler or any of our products. However, you can purchase one for your weekend trip, and it comes with a 5-year warranty for peace of mind. If you have any other questions or need assistance, feel free to ask!

- 文件實際寫了什麼：完全沒提到租借；5 年保固是對的（`warranty.pdf` p.2）
- 規則判斷：answered

### C3. Do you have a military discount?
> We currently do not offer a military discount. However, you can take advantage of our Trailpoints program to earn points on your purchases, which can be redeemed for discounts on future orders. If you have any other questions or need assistance, feel free to ask!

- 文件實際寫了什麼：完全沒提到軍人折扣；Trailpoints 是真的（`trailpoints-rewards.md`）
- 規則判斷：answered

### C4. Where is your nearest store? I want to see the Halo lantern in person.
> I'm sorry, but I don't have information about store locations. However, you can check our website for store locations or contact our customer service for assistance in finding the nearest store that carries the Halo LED Lantern.

- 文件實際寫了什麼：完全沒提到實體店。回答說「沒有資訊」，但後半段暗示有門市、網站上查得到門市
- 規則判斷：declined

### C5. Can I charge the Halo lantern with a solar panel?
> The Halo LED Lantern is designed to be charged using the included USB-C cable. It does not specify compatibility with solar panels, so it is recommended to use the provided charging method for optimal performance.

- 文件實際寫了什麼：只寫 USB-C 充電（`manual-halo-lantern.pdf` p.1–2），沒提太陽能。回答承認文件沒寫，但加了一句建議
- 規則判斷：declined

### C6. When will the Drift 20 sleeping bag be back in stock?
> I'm sorry, but I don't have information on stock availability or restock dates for the Drift 20 sleeping bag. I recommend checking our website or contacting customer service for the most accurate updates on product availability.

- 文件實際寫了什麼：完全沒提到庫存
- 規則判斷：declined

### D1. My stove arrived with a dent but I've already used it twice. Can I get a new one?
> Unfortunately, cosmetic scratches or dents are not covered under our limited warranty, as they fall under normal wear and tear. Since you've already used the stove, it would not qualify for a replacement. If you have any other issues with the stove that are not related to cosmetic damage, please let us know, and we can assist you further.

- 文件實際寫了什麼：退貨要「未使用」（`returns-policy.pdf` p.1）；「到貨就損壞」要走保固申請（同頁）；保固不含 cosmetic scratches（`warranty.pdf` p.3），但沒提到 dent，也沒說「到貨就凹」算正常磨損
- 回答直接說「不符合換新資格」，等於替客戶下了結論
- 規則判斷：declined（因為命中 "not covered"）

### D2. I was charged twice for my last order. Can you fix it?
> I'm sorry to hear about the double charge. Unfortunately, I can't directly fix billing issues, but I recommend checking your bank statement to confirm the charges. If you see two charges for the same order, please contact our customer service team directly for assistance. They will be able to help you resolve the issue.

- 文件實際寫了什麼：沒提到重複扣款。回答把問題交給客服，沒有下結論
- 規則判斷：answered（"contact our customer service team" 不在關鍵字清單裡）

### D3. Where is my order #48213? It's been 9 days.
> To track your order #48213, please check the email we sent you with the tracking link. Keep in mind that tracking can take up to 24 hours to show the first update after your order ships.
>
> If it has been 9 days since your order shipped, it should have arrived within the standard delivery timeframe of 3–6 business days for the contiguous United States. If you are in Canada, the delivery timeframe is 5–10 business days.
>
> If you still haven't received your order and the tracking information isn't showing any updates, please reach out to our customer support for further assistance.

- 文件實際寫了什麼：追蹤信、24 小時、3–6 與 5–10 個工作天都是真的（`faq.md`、`shipping-rates.pdf` p.2）。回答沒有查這筆訂單（也查不到），最後交給客服
- 規則判斷：answered
