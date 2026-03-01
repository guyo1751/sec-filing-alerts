import os
import re


def generate_html():
    summaries_file = "summaries.md"
    output_file = "docs/index.html"

    os.makedirs("docs", exist_ok=True)

    if not os.path.exists(summaries_file):
        summaries = ""
    else:
        with open(summaries_file) as f:
            summaries = f.read()

    html_entries = []
    seen_tickers = []
    entries = summaries.strip().split("\n---\n")
    for entry in entries:
        if not entry.strip():
            continue
        lines = entry.strip().split("\n")
        title = lines[0].replace("## ", "").strip()
        body = "\n".join(lines[2:]).strip()

        sections = re.split(r'\*\*(.+?)\*\*', body)
        formatted = ""
        i = 0
        while i < len(sections):
            chunk = sections[i].strip()
            if i % 2 == 1:
                formatted += f'<h3>{chunk}</h3>'
            elif chunk:
                formatted += f'<p>{chunk}</p>'
            i += 1

        ticker_match = re.match(r'^([A-Z]+)\s+—', title)
        ticker = ticker_match.group(1) if ticker_match else None
        if ticker and ticker not in seen_tickers:
            seen_tickers.append(ticker)
        html_entries.append(f"""
        <div class="card" data-ticker="{ticker or ''}">
            <h2>{title}</h2>
            {formatted}
        </div>
        """)

    cards = "".join(reversed(html_entries))
    ticker_options = "\n            ".join(
        f'<option value="{t}">{t}</option>' for t in sorted(seen_tickers)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEC Filing Summaries</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        h1 {{
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            color: #0066cc;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }}
        h2 {{
            margin-top: 0;
            color: #222;
            font-size: 1.1em;
        }}
        h3 {{
            margin-top: 16px;
            margin-bottom: 4px;
            font-size: 0.95em;
            color: #0066cc;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        p {{
            line-height: 1.7;
            color: #444;
            margin-top: 4px;
        }}
        .subtitle {{
            font-size: 0.85em;
            color: #888;
            margin-bottom: 20px;
        }}
        .filter-bar {{
            margin-bottom: 20px;
        }}
        .filter-bar label {{
            font-size: 0.9em;
            font-weight: 600;
            margin-right: 8px;
            color: #555;
        }}
        .filter-bar select {{
            font-size: 0.9em;
            padding: 6px 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: white;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <h1>SEC Filing Summaries</h1>
    <p class="subtitle">Peer companies: PR | FANG | MTDR | CTRA | DVN | SM</p>
    <div class="filter-bar">
        <label for="company-filter">Filter by company:</label>
        <select id="company-filter" onchange="filterCards(this.value)">
            <option value="ALL">All</option>
            {ticker_options}
        </select>
    </div>
    {cards}
    <script>
        function filterCards(ticker) {{
            document.querySelectorAll('.card').forEach(function(card) {{
                card.style.display = (ticker === 'ALL' || card.dataset.ticker === ticker) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>"""

    with open(output_file, "w") as f:
        f.write(html)
    print("HTML generated at docs/index.html")


if __name__ == "__main__":
    generate_html()
