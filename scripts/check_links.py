"""Check local Markdown destinations in maintained documentation, without network access."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def broken_links(document):
    text = re.sub(r"```.*?```", "", document.read_text(encoding="utf-8"), flags=re.S)
    for target in re.findall(r"\]\(([^)]+)\)", text):
        target = target.strip().strip("<>").split(' "', 1)[0]
        url = urlsplit(target)
        if url.scheme or not url.path:
            continue
        path = unquote(url.path)
        candidate = (ROOT / path.lstrip("/")) if path.startswith("/") else document.parent / path
        if not candidate.exists():
            yield f"{document.relative_to(ROOT)}: {target}"


def main():
    documents = [
        ROOT / "README.md",
        ROOT / "frontend/README.md",
        *ROOT.joinpath("docs").rglob("*.md"),
    ]
    failures = [
        failure for doc in documents if "archive" not in doc.parts for failure in broken_links(doc)
    ]
    if failures:
        raise SystemExit("Enlaces locales rotos:\n" + "\n".join(failures))
    print("Enlaces locales de la documentación: correctos.")


if __name__ == "__main__":
    main()
