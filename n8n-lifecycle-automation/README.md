# Lifecycle Marketing Automation (n8n Cloud + Google Sheets + Groq)

A behavioral-trigger marketing workflow: instead of blasting one static
message to a list, it reads each user's most recent product event **live
from a Google Sheet**, classifies them into a funnel stage, generates a
stage-appropriate message with an LLM (Groq, OpenAI-compatible API), and
writes the result back to a second Google Sheet tab.

Runs entirely in **n8n Cloud** — no local file access, no disk
dependency. The only two credentials the workflow needs are a Google
Sheets OAuth2 connection and a Groq API header-auth credential.

## Files

| File | Purpose |
|---|---|
| `n8n_workflow.json` | The importable n8n workflow |
| `sample_sheet_data.csv` | ~20 fake users with signup/first_generation/payment/inactive_3d events — paste this into the "Events" tab of your Google Sheet |

## What each node does

1. **Manual Trigger** — lets me run the workflow on demand during the demo instead of waiting on a schedule/webhook.
2. **Get Events (Google Sheets)** — reads every row from the "Events" tab (`user_id, name, email, event_type, timestamp`) using n8n's Google Sheets node with OAuth2 auth. This is the "live data" source — anyone with edit access to the sheet can add a row and the next run picks it up.
3. **Classify Users** (Code node, `runOnceForAllItems`) — the core logic:
   - Groups all event rows by `user_id`.
   - For each user, keeps only the event with the latest `timestamp` ("latest event wins" — this is what the multi-event users in the sample data demonstrate).
   - Maps that single latest event type directly to a funnel stage: `payment → paid`, `inactive_3d → at_risk`, `first_generation → activated_not_paid`, `signup → not_activated`.
   - Outputs one item per user with a new `stage` field.
4. **Switch: Route by Stage** — routes each user item to one of 4 outputs based on `stage`, using n8n's classic rules-list Switch (`value1` = `{{ $json.stage }}`, one rule per stage value).
5. **Groq: \* Message** (4x HTTP Request nodes, one per branch) — calls `POST https://api.groq.com/openai/v1/chat/completions` with `model: llama-3.3-70b-versatile`, an OpenAI-compatible `messages` array, and a **different system prompt per stage**:
   - `not_activated` — friendly activation nudge, one CTA, <80 words
   - `activated_not_paid` — value reminder + soft upgrade nudge, <80 words
   - `paid` — thank-you + referral ask, <60 words
   - `at_risk` — low-pressure win-back message, <80 words
6. **Merge** (mode: `append`, 4 inputs) — brings all 4 branches back into a single stream of items.
7. **Format Output** (Code node, `runOnceForEachItem`) — pulls `user_id`/`stage` back from the `Classify Users` node (via `$('Classify Users').item`, since by this point `$json` holds the Groq API response, not the original user record), extracts the generated text from `choices[0].message.content`, and emits `{ user_id, stage, generated_message, timestamp }`.
8. **Append Results (Google Sheets)** — writes that formatted row to the "Results" tab, so the full loop — read live data → process → write results back — is visible and real, not just console output.

## Step 1: Create the Google Sheet

1. Create a new Google Sheet (any name).
2. Rename the first tab to **`Events`** with header row:
   ```
   user_id,name,email,event_type,timestamp
   ```
3. Open `sample_sheet_data.csv`, select all, copy, and paste it into cell `A1` of the `Events` tab (Google Sheets will split it into columns automatically since it's comma-separated; if it pastes as one column instead, use **Data → Split text to columns**).
4. Create a second tab named **`Results`** with header row:
   ```
   user_id,stage,generated_message,timestamp
   ```
   Leave it otherwise empty — the workflow appends rows here on each run.
5. Copy the Sheet's ID from its URL — the long string between `/d/` and `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_SHEET_ID/edit
   ```

## Step 2: Import the workflow

1. In n8n Cloud, go to **Workflows** → **Add workflow** → **⋯** menu → **Import from File** (select `n8n_workflow.json`), or open a blank canvas and paste the JSON directly (Ctrl/Cmd+V onto the canvas also works in n8n).
2. You should see 11 nodes: Manual Trigger → Get Events (Google Sheets) → Classify Users → Switch → 4 Groq branches → Merge → Format Output → Append Results (Google Sheets).

## Step 3: Point both Sheets nodes at your sheet

Both **Get Events (Google Sheets)** and **Append Results (Google Sheets)** ship with a placeholder document ID (`YOUR_GOOGLE_SHEET_ID`) and correct default tab names (`Events` / `Results`) so they're easy to find and swap:

1. Open **Get Events (Google Sheets)** → in **Document**, either paste your Sheet ID over `YOUR_GOOGLE_SHEET_ID`, or switch the resource-locator dropdown to "From list" and pick your sheet visually. Confirm **Sheet** is set to `Events`.
2. Open **Append Results (Google Sheets)** → same thing, but confirm **Sheet** is set to `Results`.
3. On both nodes, if the tab name doesn't match your sheet exactly (case-sensitive), update it.

## Step 4: Connect the Google Sheets OAuth2 credential

1. On either Google Sheets node, click the **Credential** dropdown → **Create New Credential**.
2. Choose **Google Sheets OAuth2 API**, then **Sign in with Google** and authorize n8n against your Google account.
3. Save it (e.g. name it "Google Sheets account").
4. Go to the **other** Google Sheets node and select that same credential from its dropdown (creating it on one node doesn't auto-attach it to the other).
5. On **Append Results (Google Sheets)**, click into the **Columns** field once after the credential is connected — n8n needs a live connection to fetch your sheet's actual column headers for the mapping UI to render correctly. The four field mappings (`user_id`, `stage`, `generated_message`, `timestamp`) are pre-filled as expressions; you're just letting n8n refresh its cached schema.

## Step 5: Set up the Groq API credential

The 4 HTTP Request nodes are pre-configured to use a **Generic Credential Type → Header Auth** so the API key is never hardcoded in the workflow JSON.

1. Get a Groq API key at [console.groq.com](https://console.groq.com) → **API Keys** → **Create API Key**.
2. In n8n, on any `Groq: * Message` node, click the **Credential** dropdown → **Create New Credential** → **Header Auth**.
3. Set:
   - **Name**: `Authorization`
   - **Value**: `Bearer <your-groq-api-key>`
4. Save it (e.g. name it "Groq API Key").
5. Go to the **other 3** Groq HTTP Request nodes and select that same credential in each one's dropdown.

## Step 6: Run it end-to-end

1. Click **Execute Workflow** (fires the Manual Trigger).
2. Watch items flow: sheet rows → 20 classified users → 4 stage branches → 4 sets of Groq API calls → merged back → formatted → appended to Sheets.
3. In n8n's execution panel, click **Format Output** to see the ~20 formatted items:
   ```json
   {
     "user_id": "U004",
     "stage": "at_risk",
     "generated_message": "Hey David, we miss you! ...",
     "timestamp": "2026-09-08T12:34:56.789Z"
   }
   ```
4. Switch to your Google Sheet's **Results** tab — you should see the same ~20 rows appended there, live, in the columns `user_id | stage | generated_message | timestamp`.

## Likely interviewer questions

**"Why n8n over just writing this in Python?"**
The logic itself (classify → branch → call an LLM) is trivial in either. The point of n8n here is the *operational* surface: credentials are managed and rotated outside the code, each node's input/output is inspectable mid-run for debugging, retries/error branches are configured declaratively instead of hand-rolled `try/except`, and non-engineers (marketing ops) can read or tweak the system prompts, or even the source Sheet, without touching a deploy pipeline. I'd reach for Python if this needed heavy custom logic, tight version control on the classification algorithm, or if it were embedded inside a larger service — n8n is the right tool when the value is orchestration and visibility, not the code itself.

**"Why Groq over OpenAI/Anthropic/other providers?"**
Groq runs open models (here, Llama 3.3 70B) on their LPU hardware, so latency per call is very low — that matters when you're generating messages for thousands of users in a batch window, not just one chat reply. It's also OpenAI-compatible, so the HTTP Request node (or credential setup) is a drop-in swap if we ever want to point at a different provider or self-hosted endpoint later. The tradeoff is less nuanced instruction-following than the frontier closed models, which is an acceptable tradeoff for short, template-constrained marketing copy but I'd reconsider for anything requiring more reasoning or brand-voice precision.

**"How would this scale to 10,000 users?"**
A few changes: (1) Google Sheets itself becomes the bottleneck well before 10k rows (read/write quotas, no real indexing) — I'd move the event source to a real database or warehouse and the results log to a proper table, keeping Sheets only as a demo-friendly stand-in; (2) the HTTP Request nodes would need a rate-limit-aware loop — n8n's "Split in Batches" node plus a wait/backoff, since Groq (like any provider) rate-limits requests per minute; (3) I'd move from a Manual Trigger to a Schedule Trigger or a webhook fired by the event source; (4) I'd add error-branch handling (see next question) so one bad row or one failed API call doesn't stop the whole run; (5) at that volume I'd also batch multiple users per LLM call where the prompt allows it, to cut total request count and cost.

**"What happens if the LLM call or the Sheets write fails?"**
As configured, a node failure stops that branch's execution for that item (n8n's default "Stop Workflow" behavior). I'd explicitly enable **Continue on Fail / error output** on the 4 Groq nodes and on the final Append Results node, routing failures to a small error-handling branch — log the user_id and stage with a placeholder/fallback message (or requeue for retry with backoff) instead of silently dropping the user. I'd also add basic response validation in **Format Output** (check `choices?.[0]?.message?.content` exists before trusting it), since a rate-limited or malformed Groq response would otherwise throw inside that Code node and take down the branch anyway.

**"Why Google Sheets instead of a real database?"**
For a demo, it's the fastest way to make "live data in, live data out" visibly real to a non-technical audience — anyone can open the sheet, edit a row, rerun, and watch the Results tab update, with zero infra to stand up. It's a deliberate demo-scale choice, not a production one: Sheets has row/read/write quotas, no transactional guarantees, and gets slow well before tens of thousands of rows. In production I'd swap the two Google Sheets nodes for a Postgres/warehouse read and write — the rest of the workflow (classification, routing, LLM calls, formatting) doesn't change at all, which is exactly the kind of swap n8n makes cheap since the data source is isolated to two nodes.
