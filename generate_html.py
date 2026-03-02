import os
import re


def parse_entries(summaries):
    """Parse summaries.md into a list of dicts with ticker, form, date, body.

    Only splits on '---' lines that are immediately followed by a '## TICKER'
    header, so inline horizontal rules inside a summary body are ignored.
    """
    # Split only on the pattern: newline + --- + newline + ## (entry header)
    raw_entries = re.split(r'\n---\n(?=##\s)', summaries)

    entries = []
    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue

        lines = entry.split("\n")
        first_line = lines[0]

        # Must start with ## TICKER — FORM — DATE
        if not first_line.startswith("## "):
            continue

        title_line = first_line[3:].strip()  # strip leading '## '
        parts = [p.strip() for p in title_line.split("—")]
        if len(parts) == 3:
            ticker, form, date = parts[0], parts[1], parts[2]
        else:
            # Doesn't match expected format — skip
            continue

        # Body starts after the title line and optional blank line
        body_start = 2 if len(lines) > 1 and lines[1].strip() == "" else 1
        body = "\n".join(lines[body_start:]).strip()

        entries.append({"ticker": ticker, "form": form, "date": date, "body": body})

    # Sort newest first
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def body_to_html(body):
    """Convert markdown body text to HTML."""
    # Strip any stray leading # headings the model may have added
    body = re.sub(r'^#{1,3} .+\n?', '', body, flags=re.MULTILINE)

    # Split on **Section Header** markers
    sections = re.split(r'\*\*(.+?)\*\*', body)
    html = ""
    for i, chunk in enumerate(sections):
        chunk = chunk.strip()
        if not chunk:
            continue
        if i % 2 == 1:
            html += f'<h3>{chunk}</h3>'
        else:
            # Preserve line breaks as separate paragraphs
            for para in chunk.split("\n"):
                para = para.strip()
                if para:
                    # Convert markdown bullet `-` or `*` at line start
                    if re.match(r'^[-*] ', para):
                        para = para[2:]
                        html += f'<li>{para}</li>'
                    else:
                        html += f'<p>{para}</p>'
    return html


def generate_html():
    summaries_file = "summaries.md"
    output_file = "docs/index.html"

    os.makedirs("docs", exist_ok=True)

    if not os.path.exists(summaries_file):
        entries = []
    else:
        with open(summaries_file) as f:
            entries = parse_entries(f.read())

    tickers = sorted({e["ticker"] for e in entries if e["ticker"]})

    ticker_options = '<option value="all">All Companies</option>\n'
    ticker_options += "\n".join(
        f'        <option value="{t}">{t}</option>' for t in tickers
    )

    cards_html = ""
    for e in entries:
        body_html = body_to_html(e["body"])
        cards_html += f"""
        <div class="card" data-ticker="{e['ticker']}">
            <div class="card-header">
                <span class="ticker-badge">{e['ticker']}</span>
                <span class="form-badge">{e['form']}</span>
                <span class="date-badge">{e['date']}</span>
            </div>
            {body_html}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEC Filing Summaries</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 960px;
            margin: 0 auto;
            padding: 24px 20px;
            background: #f0f2f5;
            color: #333;
        }}
        h1 {{
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            color: #0066cc;
            margin-bottom: 6px;
        }}
        .subtitle {{
            font-size: 0.85em;
            color: #888;
            margin-bottom: 20px;
        }}
        .controls {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}
        .controls label {{
            font-weight: 600;
            font-size: 0.9em;
            color: #555;
        }}
        .controls select {{
            padding: 8px 12px;
            border: 1px solid #ccd0d6;
            border-radius: 6px;
            font-size: 0.95em;
            background: white;
            cursor: pointer;
            min-width: 160px;
        }}
        #count {{
            font-size: 0.85em;
            color: #888;
            margin-left: auto;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 18px 22px;
            margin-bottom: 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.07);
            border-left: 4px solid #0066cc;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 14px;
        }}
        .ticker-badge {{
            background: #0066cc;
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.9em;
            letter-spacing: 0.04em;
        }}
        .form-badge {{
            background: #e8f0fe;
            color: #1a56cc;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .date-badge {{
            color: #888;
            font-size: 0.85em;
            margin-left: auto;
        }}
        h3 {{
            margin: 14px 0 4px;
            font-size: 0.82em;
            color: #0066cc;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}
        p {{
            line-height: 1.7;
            color: #444;
            margin: 4px 0 8px;
        }}
        li {{
            line-height: 1.7;
            color: #444;
            margin: 2px 0;
            margin-left: 18px;
        }}
        .hidden {{ display: none; }}
    </style>
</head>
<body>
    <h1>SEC Filing Summaries</h1>
    <p class="subtitle">Peer companies: PR | FANG | MTDR | CTRA | DVN | SM</p>

    <div class="controls">
        <label for="company-filter">Company:</label>
        <select id="company-filter" onchange="filterCards()">
        {ticker_options}
        </select>
        <span id="count"></span>
    </div>

    <div id="cards">
    {cards_html}
    </div>

    <script>
        function filterCards() {{
            const val = document.getElementById('company-filter').value;
            const cards = document.querySelectorAll('#cards .card');
            let visible = 0;
            cards.forEach(card => {{
                const show = val === 'all' || card.dataset.ticker === val;
                card.classList.toggle('hidden', !show);
                if (show) visible++;
            }});
            document.getElementById('count').textContent =
                visible === cards.length ? `${{cards.length}} filings` : `${{visible}} of ${{cards.length}} filings`;
        }}
        filterCards();
    </script>
</body>
</html>"""

    with open(output_file, "w") as f:
        f.write(html)
    print(f"HTML generated at {output_file} ({len(entries)} entries)")


if __name__ == "__main__":
    generate_html()
