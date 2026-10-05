# Cheat sheet: 10 questions

Glance at the bold word, say the sentence.

Cost figures match the customer document. The "about 10 seconds" in number 9 comes from the prep doc only (9.5 seconds measured); time it once in the demo before quoting it.

---

## 1. Why custom, not off-the-shelf RAG?

- **Concede:** RAG would work for a chatbot.
- **Thesis:** this is about valuation, not text passages.
- **Facts:** the pipeline pulls facts out of documents.
- **Models:** facts land where machine learning runs the valuation.
- **Check:** each fact is checked against your records for discrepancies.
- **Example:** inspection found water damage the county didn't show; value withheld.

## 2. How does a PDF become citable?

- **Storage:** PDF lands in Cloud Storage.
- **Layout Parser:** splits into blocks, keeps each page number.
- **Gemini:** reads the blocks, extracts facts.
- **Embeddings:** paragraphs become vectors for search.
- **Check, then BigQuery:** consistency check, then load.
- **Document, page, quote:** every fact carries all three.
- **Example:** 1,240 sq ft traces to the inspection report, page 2.

*Blocks, not entities. Gemini makes facts, not vectors.*

## 3. Why Document AI when Gemini reads PDFs?

- **Concede:** you could use Gemini.
- **Reason:** page numbers and the same blocks every run, so citations are auditable.
- **BigQuery:** easy lineage and citation.
- **Cost:** a cent a page, worth it for the audit trail.

*Not cheaper than Gemini. Not a "specialised" parser.*

## 4. Why BigQuery for vectors?

- **Simple:** it's pretty simple.
- **Together:** vectors, typed facts and tabular data in one place, for lineage.
- **Models:** BigQuery has the machine learning for the valuation.
- **Scale:** scales well; add a vector index if needed.
- **Concede:** other vector databases work; this one is straightforward.

*If pressed: retrieval is one small file; could swap in Vertex AI Vector Search.*

## 5. How do you stop made-up numbers?

- **Never:** the language model never produces the number.
- **Models:** the value comes from machine learning on extracted facts.
- **Explains:** the language model only explains the result.
- **Withheld:** if the engine gives no value, the model never gets it, so it can't leak.
- **Queue:** discrepancies go to a review queue.
- **Story:** early on, it added two numbers into a total found in no document.

## 6. How does it scale to 50,000 documents?

- **Honest:** there are parts I'd augment.
- **Storage:** fine as it is.
- **Pub/Sub:** triggers batch processing in Document AI.
- **Gemini:** reserve capacity.
- **Cloud Run:** review list is in the app's memory, so one copy only. Move it to BigQuery, then scale out.
- **Vector index:** in BigQuery, for faster retrieval.

*Not "built to scale". Not "just a setting".*

## 7. How do you secure this?

- **Today:** no sign-in; users pick a name from a menu.
- **Sign-in:** a real identity provider.
- **Identity-Aware Proxy:** identities and groups limit access.
- **Cloud Armor:** firewall against standard API attacks.
- **Model Armor:** screens for prompt injection and off-task use.
- **BigQuery:** row-level and column-level security.
- **Service accounts:** least privilege.
- **VPC Service Controls:** data can't leave BigQuery or Vertex AI.

**Prompt injection (finish with this):**

- **Risk:** a PDF from an outside party carrying hidden instructions.
- **Assume it gets through:** so limit what the model can do.
- **Read-only:** it can't set a value.
- **Two people:** it can't approve a change.
- **Held:** a planted fact that contradicts the record waits for review.

## 8. What does it cost?

- **Open:** the slide has the detail; in round numbers...
- **First run:** a property packet of about 60 pages costs about 85 cents.
- **After that:** each run is about half a cent.
- **Line:** the price goes up with pages, not with questions.

*Backup: 1.4 cents a page, a third of a cent an answer. Demo house, 4 pages: 6 cents.*
*Pilot county: $1,350 once for 100,000 pages, then $110 a month for 20,000 questions.*
*Cloud list prices only; no staff cost. Don't compare with the price of an appraisal.*

## 9. What's the ROI?

- **Honest:** I don't have your numbers, so no exact comparison.
- **Three ways:** speed, risk and reuse.
- **Speed:** a new document is ready in about 10 seconds, versus someone keying it in.
- **Risk:** no value shown while evidence conflicts, so fewer loans reworked or bought back.
- **Reuse:** the same facts feed analytics and model training, not just the chat.
- **Pilot:** measure rework rate and analyst time, against about 85 cents a packet.
- **Ask back:** what does a reworked loan cost you today?

## 10. What's the weakest part?

- **First:** the review system.
- **Why:** built to show how discrepancies and bad numbers get handled, but held in memory; a restart loses it and there's no audit log.
- **Second:** the app uses a simple price formula, not the model I trained.
- **Third:** documents link to properties by a lookup file, not real matching.
- **Close:** none of these changes the architecture; they're the first 90 days of hardening.

*Three gaps, no more. If pressed: the automatic check only compares like with like; the addition is flagged by a person.*

---

## Two demo houses

- **18 Larkspur (automatic):** inspection found water damage, county showed average condition. Fact held, value withdrawn, two approvals.
- **14 Larkspur (flagged by a person):** county says 1,240 sq ft, inspection page 2 shows an 840 sq ft addition. System shows it with the citation; reviewer flags; two approvals.
