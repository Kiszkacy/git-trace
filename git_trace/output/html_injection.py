from pathlib import Path

_ASSETS: Path = Path(__file__).parent / "assets"


def _load_asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def _inject(html_path: str, snippet: str):
    text = Path(html_path).read_text(encoding="utf-8")
    if "</body>" in text:
        text = text.replace("</body>", snippet + "\n</body>", 1)
        Path(html_path).write_text(text, encoding="utf-8")


def inject_analysis_controls(html_path: str):
    _inject(html_path, _load_asset("analysis_controls.html"))


def inject_analysis_legend(html_path: str):
    _inject(html_path, _load_asset("analysis_legend.html"))


def inject_pick_controls(html_path: str):
    _inject(html_path, _load_asset("pick_controls.html"))


def inject_pick_legend(html_path: str):
    _inject(html_path, _load_asset("pick_legend.html"))


def inject_styling(html_path: str):
    _inject(html_path, _load_asset("styling.html"))
