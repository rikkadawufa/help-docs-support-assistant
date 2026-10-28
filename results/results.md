# Eval results

> All questions and documents are made up (fictional store "Cinderpeak Outdoor"). The baseline is a deliberately simple RAG written for this demo, not a real product. Every number below is counted by `scripts/collect_results.py` from the run logs.

- LLM mode: `live`, chat model: `gpt-4o-mini`
- Logs: `20261029-044207-grounded.jsonl`, `20261029-044207-baseline.jsonl`, `20261029-061753-scenario-update.jsonl`, `20261029-061802-scenario-llm-error.jsonl`

## Before / after

| What we checked | Baseline (simple RAG) | This assistant |
|---|---|---|
| Answerable questions (A+B): correct answer | 12/12 (shows no sources) | 12/12 with a checked citation to the right file and page |
| Trap questions (C): answered anyway | 4/6 | 0/6 |

Account-specific questions (D) are listed per question below, not in this table.

## Grounded assistant, question by question

| ID | Question | Status | Result | Note |
|---|---|---|---|---|
| A1 | How many days do I have to return something? | answered | pass | correct, cited returns-policy.pdf p.1 |
| A2 | Once you get my return, how long until I see the refund? | answered | pass | correct, cited returns-policy.pdf p.2 |
| A3 | I bought an extra propane canister and never used it. Can I send it back? | answered | pass | correct, cited returns-policy.pdf p.1 |
| A4 | It's going to rain on our trip. Is it OK to cook with the Ember 2 inside the tent? | answered | pass | correct, cited manual-ember-2-stove.pdf p.2 |
| A5 | How should I wash my Drift 20 sleeping bag? | answered | pass | correct, cited manual-drift-20-sleeping-bag.pdf p.2 |
| A6 | My lantern stopped turning on after two months. How do I make a warranty claim? | answered | pass | correct, cited warranty.pdf p.3 |
| A7 | Can I use two promo codes on the same order? | answered | pass | correct, cited gift-cards-and-promos.md > Promo codes |
| A8 | Do you ship to the UK? | answered | pass | correct, cited international-shipping.md > Where we ship |
| B1 | What's the warranty on the Glacier 45 cooler? | answered | pass | correct, cited warranty.pdf p.2 |
| B2 | How much is standard shipping on a $50 order in the US? | answered | pass | correct, cited shipping-rates.pdf p.1 |
| B3 | How long does the Halo lantern last on the low setting? | answered | pass | correct, cited manual-halo-lantern.pdf p.1 |
| B4 | How long is the battery inside my Halo lantern covered under warranty? | answered | pass | correct, cited warranty.pdf p.2 |
| C1 | Do you price match if I find the Ember 2 cheaper somewhere else? | handoff | pass | handoff (model_declined) |
| C2 | Can I rent a Glacier 45 cooler for a weekend trip? | handoff | pass | handoff (model_declined) |
| C3 | Do you have a military discount? | handoff | pass | handoff (low_relevance) |
| C4 | Where is your nearest store? I want to see the Halo lantern in person. | handoff | pass | handoff (model_declined) |
| C5 | Can I charge the Halo lantern with a solar panel? | handoff | pass | handoff (model_declined) |
| C6 | When will the Drift 20 sleeping bag be back in stock? | handoff | pass | handoff (model_declined) |
| D1 | My stove arrived with a dent but I've already used it twice. Can I get a new one? | handoff | pass | handoff (low_relevance) |
| D2 | I was charged twice for my last order. Can you fix it? | handoff | pass | handoff (model_declined) |
| D3 | Where is my order #48213? It's been 9 days. | handoff | pass | handoff (model_declined) |

## Baseline, question by question

| ID | Question | Verdict | Answer (first 140 chars) |
|---|---|---|---|
| A1 | How many days do I have to return something? | facts match | You have 30 days from the delivery date to return most items for a full refund. |
| A2 | Once you get my return, how long until I see the refund? | facts match | Once we receive and inspect your return, refunds are issued to the original payment method within 5–7 business days. You will receive an ema |
| A3 | I bought an extra propane canister and never used it. Can I send it back? | facts match | No, you cannot return the propane canister. Fuel canisters cannot be returned for safety and hygiene reasons, even if they are unused. |
| A4 | It's going to rain on our trip. Is it OK to cook with the Ember 2 inside the tent? | facts match | No, it is not safe to cook with the Ember 2 inside the tent or in any enclosed space. The stove produces carbon monoxide, which can be deadl |
| A5 | How should I wash my Drift 20 sleeping bag? | facts match | To wash your Drift 20 sleeping bag, follow these steps: 1. Use a front-loading washing machine only, as top-loading machines with an agitato |
| A6 | My lantern stopped turning on after two months. How do I make a warranty claim? | facts match | To make a warranty claim for your Halo LED Lantern, please follow these steps: 1. **Email**: Send an email to warranty@cinderpeak.example. 2 |
| A7 | Can I use two promo codes on the same order? | facts match | No, you cannot use two promo codes on the same order. Only one promo code can be applied per order, and they cannot be combined. |
| A8 | Do you ship to the UK? | facts match | No, we do not ship to the UK. We only ship to the United States and Canada. |
| B1 | What's the warranty on the Glacier 45 cooler? | facts match | The Glacier 45 cooler comes with a limited warranty of 5 years against defects in materials and workmanship. This warranty applies to the or |
| B2 | How much is standard shipping on a $50 order in the US? | facts match | For a $50 order in the contiguous United States, standard shipping would be $9.95. |
| B3 | How long does the Halo lantern last on the low setting? | facts match | The Halo LED Lantern lasts for 40 hours on the low setting. |
| B4 | How long is the battery inside my Halo lantern covered under warranty? | facts match | The built-in rechargeable battery inside your Halo LED Lantern is covered under warranty for 1 year, regardless of the product line's warran |
| C1 | Do you price match if I find the Ember 2 cheaper somewhere else? | answered (human) | Cinderpeak Outdoor does not have a price matching policy. If you have any other questions or need assistance with ordering parts for the Emb |
| C2 | Can I rent a Glacier 45 cooler for a weekend trip? | answered (human) | I'm sorry, but we do not offer rentals for the Glacier 45 cooler or any of our products. However, you can purchase one for your weekend trip |
| C3 | Do you have a military discount? | answered (human) | We currently do not offer a military discount. However, you can take advantage of our Trailpoints program to earn points on your purchases,  |
| C4 | Where is your nearest store? I want to see the Halo lantern in person. | answered (human (rule said declined)) | I'm sorry, but I don't have information about store locations. However, you can check our website for store locations or contact our custome |
| C5 | Can I charge the Halo lantern with a solar panel? | declined (human) | The Halo LED Lantern is designed to be charged using the included USB-C cable. It does not specify compatibility with solar panels, so it is |
| C6 | When will the Drift 20 sleeping bag be back in stock? | declined (human) | I'm sorry, but I don't have information on stock availability or restock dates for the Drift 20 sleeping bag. I recommend checking our websi |
| D1 | My stove arrived with a dent but I've already used it twice. Can I get a new one? | answered (human (rule said declined)) | Unfortunately, cosmetic scratches or dents are not covered under our limited warranty, as they fall under normal wear and tear. Since you've |
| D2 | I was charged twice for my last order. Can you fix it? | declined (human (rule said answered)) | I'm sorry to hear about the double charge. Unfortunately, I can't directly fix billing issues, but I recommend checking your bank statement  |
| D3 | Where is my order #48213? It's been 9 days. | declined (human (rule said answered)) | To track your order #48213, please check the email we sent you with the tracking link. Keep in mind that tracking can take up to 24 hours to |

## E. Document update (returns policy 30 -> 14 days)

| Step | Ingest | Status | Result | Answer |
|---|---|---|---|---|
| E1-before | updated 0, unchanged 16 | answered | pass | You can return most items within 30 days of delivery for a full refund. |
| E1-after | updated 1, unchanged 15 | answered | pass | You can return most items within 14 days of delivery for a full refund. |

## F. AI service failure

| Step | Status | Reason | Alert | Result |
|---|---|---|---|---|
| F1 | degraded | llm_error | llm_error/sent | pass |
| F1-next | answered | - | - | pass |
