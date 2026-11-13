# Gemini email workflow

A small email workflow built with LangGraph, LangChain, Gemini 3.6 Flash, and Streamlit. Enter the recipient and describe the email. Gemini plans, drafts, and reviews the message. Gmail SMTP sends it only if the review approves the draft; the page then shows a success message and toast.

## Workflow nodes

1. **Plan** — organize the requested email and tone.
2. **Draft email** — create a subject and plain-text body.
3. **Review** — check the draft against the request and recipient.
4. **Send email** — send only an approved draft through Gmail SMTP.
5. **Final status** — report `SENT`, `NEEDS_REVIEW`, or `FAILED`.

The webpage highlights the active node while it runs and marks completed, skipped, or failed nodes. A reviewer rejection skips sending.

## Configure credentials

Use the variable names in `.env.example` and add the mail settings to your existing local `.env` without replacing your Gemini key:

- `GEMINI_API_KEY` — your Gemini API key.
- `SMTP_SENDER_EMAIL` — the Gmail account to send from.
- `SMTP_APP_PASSWORD` — a Gmail app password for that account.

Do not commit `.env` or put credentials in Python source files. If an app password was previously hard-coded in another script, revoke it and use a newly generated one.

## Start the webpage

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Enter the recipient and email request, then choose **Draft, review and send email**. A success toast appears only after Gmail confirms the message was sent.

## Run in the terminal

```powershell
python main.py
```

