import json
import os
import requests
import time
from anthropic import Anthropic

NTFY_TOPIC = "SECAlertsPRMidland"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TRACKER_FILE = "tracker.json"
COMPANIES_FILE = "companies.json"

client = Anthropic(api_key=ANTHROPIC_API_KEY)

def get_cik_from_ticker(ticker):
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": "SECAlerts yourname@email.com"}
    resp = requests.get(url, headers=headers)
    data = resp.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None

def get_recent_filings(cik):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    headers = {"User-Agent": "SECAlerts yourname@email.com"}
    resp = requests.get(url, headers=headers)
    data = resp.json()
    filings = data.get("filings", {}).get("recent", {})
    results = []
    for i in range(len(filings.get("accessionNumber", []))):
        results.append({
            "accessionNumber": filings["accessionNumber"][i],
            "form": filings["form"][i],
            "filingDate": filings["filingDate"][i],
            "primaryDocument": filings["primaryDocument"][i],
        })
    return results

def get_filing_text(cik, accession_number, primary_doc):
    accession_clean = accession_number.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_clean}/{primary_doc}"
    headers = {"User-Agent": "SECAlerts yourname@email.com"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        # Strip HTML tags roughly
        text = resp.text
        import re
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text[:15000]  # Limit to first 15k chars to control cost
    return None

INSIDER_FORMS = {"3", "4", "5", "144", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"}
EARNINGS_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}
EVENT_FORMS = {"8-K", "8-K/A"}


def _build_prompt(ticker, form_type, filing_date, text):
    base = f"SEC {form_type} filing from {ticker} (filed {filing_date}).\n\nFiling text:\n{text}"
    no_title = "Do NOT start your response with a title or heading. Begin directly with the first section bold header."

    if form_type in INSIDER_FORMS:
        return f"""You are a senior equity analyst specializing in insider transaction analysis.
Analyze this {base}

{no_title} Provide a concise summary using exactly this structure:

**Transaction Summary**
Who filed, what form, and the nature of the transaction(s) in one to two sentences.

**Transaction Details**
List each transaction: date, shares/units, price, transaction code (buy/sell/gift/award/tax-withhold), and total dollar value where calculable.

**Post-Transaction Holdings**
Insider's remaining ownership after the transaction(s).

**Market Signal**
Is this discretionary or non-discretionary (10b5-1 plan, tax withholding, estate planning)? What, if anything, does this signal about insider sentiment? Keep to 2-3 sentences."""

    if form_type in EARNINGS_FORMS:
        return f"""You are a senior oil & gas equity analyst.
Analyze this {base}

{no_title} Provide a detailed summary using exactly this structure:

**Overview**
One sentence: filing type, reporting period, and company.

**Key Financials**
Revenue, net income, EPS, EBITDA, and free cash flow — actuals vs prior period. Note any beats or misses vs expectations if mentioned.

**Production & Operations**
Total production volumes (BOE/d), oil/gas/NGL breakdown, capital expenditure, and any notable operational updates or asset changes.

**Guidance & Outlook**
Full-year or next-quarter guidance figures, any changes from prior guidance, and management's commentary on macro outlook.

**Risks & Concerns**
Key risk factors, debt levels, hedging exposure, or anything that could negatively impact the business.

**Market Moving Items**
Anything surprising — beats/misses, strategic announcements, one-time items, or guidance changes likely to move the stock."""

    if form_type in EVENT_FORMS:
        return f"""You are a senior oil & gas equity analyst.
Analyze this {base}

{no_title} Provide a focused summary using exactly this structure:

**Event Summary**
What happened? One to two sentences describing the specific event this 8-K reports.

**Key Details**
The most important facts, figures, or terms (e.g., deal size, production impact, pricing, parties involved).

**Financial Impact**
Quantified financial impact if disclosed — revenue, costs, charges, proceeds, etc.

**Market Moving Assessment**
Is this material? Bullish, bearish, or neutral signal? Why? Keep to 3-4 sentences."""

    return f"""You are a senior equity analyst.
Analyze this {base}

{no_title} Provide a brief summary using exactly this structure:

**Filing Purpose**
One sentence explaining what this filing is and why it was submitted.

**Key Content**
The most important information disclosed — 3 to 5 bullet points.

**Investor Relevance**
Is this filing material to investors? Any action required or notable disclosures? 2-3 sentences."""


def summarize_filing(ticker, form_type, filing_date, text):
    prompt = _build_prompt(ticker, form_type, filing_date, text)
    max_tokens = 1800 if form_type in EARNINGS_FORMS else 800

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
    
def send_ntfy_alert(ticker, form_type, filing_date, summary, accession_number):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    title = f"{ticker} filed {form_type} on {filing_date}"
    edgar_link = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={form_type}&dateb=&owner=include&count=5"
    body = f"{summary}\n\nView on EDGAR: {edgar_link}"
    requests.post(url, data=body.encode("utf-8"), headers={
        "Title": title,
        "Priority": "default",
        "Tags": "chart_with_upwards_trend"
    })

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    return {}

def save_tracker(tracker):
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)

def save_summary_to_file(ticker, form_type, filing_date, summary):
    summary_file = "summaries.md"
    with open(summary_file, "a") as f:
        f.write(f"\n---\n")
        f.write(f"## {ticker} — {form_type} — {filing_date}\n\n")
        f.write(f"{summary}\n")

def main():
    with open(COMPANIES_FILE) as f:
        raw = f.read()
        print(f"companies.json contents: '{raw}'")
        tickers = json.loads(raw)["tickers"]

    tracker = load_tracker()

    for ticker in tickers:
        print(f"Checking {ticker}...")
        cik = get_cik_from_ticker(ticker)
        if not cik:
            print(f"  Could not find CIK for {ticker}")
            continue

        filings = get_recent_filings(cik)
        seen = tracker.get(ticker, [])
        new_filings = [f for f in filings if f["accessionNumber"] not in seen]

        for filing in new_filings[:5]:
            print(f"  New filing: {filing['form']} on {filing['filingDate']}")
            text = get_filing_text(cik, filing["accessionNumber"], filing["primaryDocument"])
            if text:
                summary = summarize_filing(ticker, filing["form"], filing["filingDate"], text)
                send_ntfy_alert(ticker, filing["form"], filing["filingDate"], summary, filing["accessionNumber"])
                save_summary_to_file(ticker, filing["form"], filing["filingDate"], summary)
                print(f"  Alert sent for {filing['form']}")
            seen.append(filing["accessionNumber"])
            time.sleep(1)

        tracker[ticker] = seen[-100:]
        save_tracker(tracker)
        time.sleep(2)

    print("Done.")

if __name__ == "__main__":
    main()
