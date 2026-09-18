"""Check that documentation links and heading anchors resolve, and list code identifiers the docs mention
that cannot be found in oeisbot/, tests/ or dashboard/src/.

    .venv\\Scripts\\python scripts\\check_docs.py

Missing files and anchors are real problems. Identifier hits need judgment: the docs also name Windows API
flags in short form, built-in exceptions and illustrative names that are not in the code.
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent


def anchors(text: str) -> set[str]:
    """GitHub-style heading anchors: lowercase, punctuation other than - and _ dropped, spaces to -."""
    out, in_code = set(), False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and not in_code:
            out.add(re.sub(r"[^\w\- ]", "", m.group(2).strip().lower()).replace(" ", "-"))
    return out


def main() -> int:
    docs = [ROOT / "README.md", ROOT / "CLAUDE.md", *sorted((ROOT / "docs").glob("*.md"))]
    link_problems = 0
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, frag = target.partition("#")
            dest = (doc.parent / path).resolve() if path else doc
            if not dest.exists():
                print(f"LINK   {doc.name}: missing file {target}")
                link_problems += 1
            elif frag and dest.suffix == ".md" and frag not in anchors(dest.read_text(encoding="utf-8")):
                print(f"LINK   {doc.name}: missing anchor {target}")
                link_problems += 1

    code = [*(ROOT / "oeisbot").rglob("*.py"), *(ROOT / "tests").glob("*.py"), *(ROOT / "scripts").glob("*.py"),
            *(ROOT / "dashboard" / "src").glob("*.ts*")]
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in code)
    seen = set()
    for doc in docs:
        for ident in re.findall(r"`([A-Za-z_][\w.]*)(?:\(\))?`", doc.read_text(encoding="utf-8")):
            last = ident.split(".")[-1]
            if (doc.name, ident) in seen or len(last) <= 3:
                continue
            if "_" in last or "." in ident or any(c.isupper() for c in last[1:]):
                seen.add((doc.name, ident))
                if not re.search(rf"{re.escape(last)}", source):
                    print(f"IDENT  {doc.name}: not found in code: {ident}")
    print(f"link problems: {link_problems}")
    return 1 if link_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
