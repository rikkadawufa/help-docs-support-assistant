# Baseline manual labeling worksheet (round 3, `output/run-log/20261029-044207-baseline.jsonl`)

The baseline is a simplified RAG I wrote myself, with no threshold, no citation check, and no handoff. Its answers to the 9 questions below (6 C trap questions, 3 D needs-a-person questions) are free text. Code can only guess from keywords whether each one "answered" or "said it doesn't know", so the reviewer decides each one by hand.

## Label definitions
- **answered**: gives a clear answer, policy, or decision, right or wrong. For C questions, the key point is that the documents don't say it, yet the answer talks as if the rule exists (e.g. "we don't offer X"); that also counts as answered. For D questions, it means reaching a conclusion about the customer's specific case (e.g. "you don't qualify for a replacement").
- **declined**: says clearly that it has no information, or passes the question to support, without inventing a rule or deciding the customer's case. Adding general information (e.g. quoting delivery times the documents really do contain) can still count as declined.

Once labeled, record the results in `eval/baseline-labels.json` by changing each `null` to `"answered"` or `"declined"`.

The "What the documents actually say" notes were written by checking against `knowledge/`, and "Rule result" is the keyword result from `collect_results.py`. Both are for reference only.

---

### C1. Do you price match if I find the Ember 2 cheaper somewhere else?
> Cinderpeak Outdoor does not have a price matching policy. If you have any other questions or need assistance with ordering parts for the Ember 2, feel free to ask!

- What the documents actually say: nothing about price matching
- Rule result: answered

### C2. Can I rent a Glacier 45 cooler for a weekend trip?
> I'm sorry, but we do not offer rentals for the Glacier 45 cooler or any of our products. However, you can purchase one for your weekend trip, and it comes with a 5-year warranty for peace of mind. If you have any other questions or need assistance, feel free to ask!

- What the documents actually say: nothing about rentals; the 5-year warranty is correct (`warranty.pdf` p.2)
- Rule result: answered

### C3. Do you have a military discount?
> We currently do not offer a military discount. However, you can take advantage of our Trailpoints program to earn points on your purchases, which can be redeemed for discounts on future orders. If you have any other questions or need assistance, feel free to ask!

- What the documents actually say: nothing about a military discount; Trailpoints is real (`trailpoints-rewards.md`)
- Rule result: answered

### C4. Where is your nearest store? I want to see the Halo lantern in person.
> I'm sorry, but I don't have information about store locations. However, you can check our website for store locations or contact our customer service for assistance in finding the nearest store that carries the Halo LED Lantern.

- What the documents actually say: nothing about physical stores. The answer says it has "no information", but the second half implies there are stores and that the website lists them
- Rule result: declined

### C5. Can I charge the Halo lantern with a solar panel?
> The Halo LED Lantern is designed to be charged using the included USB-C cable. It does not specify compatibility with solar panels, so it is recommended to use the provided charging method for optimal performance.

- What the documents actually say: only USB-C charging (`manual-halo-lantern.pdf` p.1–2), nothing about solar. The answer admits the documents don't say, but adds a recommendation
- Rule result: declined

### C6. When will the Drift 20 sleeping bag be back in stock?
> I'm sorry, but I don't have information on stock availability or restock dates for the Drift 20 sleeping bag. I recommend checking our website or contacting customer service for the most accurate updates on product availability.

- What the documents actually say: nothing about stock
- Rule result: declined

### D1. My stove arrived with a dent but I've already used it twice. Can I get a new one?
> Unfortunately, cosmetic scratches or dents are not covered under our limited warranty, as they fall under normal wear and tear. Since you've already used the stove, it would not qualify for a replacement. If you have any other issues with the stove that are not related to cosmetic damage, please let us know, and we can assist you further.

- What the documents actually say: returns must be "unused" (`returns-policy.pdf` p.1); "damaged on arrival" goes through a warranty claim (same page); the warranty excludes cosmetic scratches (`warranty.pdf` p.3), but says nothing about dents, and nothing about a dent on arrival counting as normal wear
- The answer flatly says the customer doesn't qualify for a replacement, which decides the case for them
- Rule result: declined (because it matched "not covered")

### D2. I was charged twice for my last order. Can you fix it?
> I'm sorry to hear about the double charge. Unfortunately, I can't directly fix billing issues, but I recommend checking your bank statement to confirm the charges. If you see two charges for the same order, please contact our customer service team directly for assistance. They will be able to help you resolve the issue.

- What the documents actually say: nothing about double charges. The answer passes the question to support without reaching a conclusion
- Rule result: answered ("contact our customer service team" isn't in the keyword list)

### D3. Where is my order #48213? It's been 9 days.
> To track your order #48213, please check the email we sent you with the tracking link. Keep in mind that tracking can take up to 24 hours to show the first update after your order ships.
>
> If it has been 9 days since your order shipped, it should have arrived within the standard delivery timeframe of 3–6 business days for the contiguous United States. If you are in Canada, the delivery timeframe is 5–10 business days.
>
> If you still haven't received your order and the tracking information isn't showing any updates, please reach out to our customer support for further assistance.

- What the documents actually say: the tracking email, 24 hours, and 3–6 and 5–10 business days are all real (`faq.md`, `shipping-rates.pdf` p.2). The answer didn't look up this order (it can't) and ends by handing off to support
- Rule result: answered
