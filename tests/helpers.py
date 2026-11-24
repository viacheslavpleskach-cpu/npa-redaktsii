"""Спільні засоби для офлайн-тестів sync_api_v4_1 (без мережі).

Автор: В'ячеслав Плескач.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

import requests
from requests.structures import CaseInsensitiveDict

HERE = Path(__file__).resolve().parent
SKRYPTY = HERE.parent / "skrypty"


def load_sync():
    spec = importlib.util.spec_from_file_location("sync_api_v4_1", SKRYPTY / "sync_api_v4_1.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_api_v4_1"] = mod
    spec.loader.exec_module(mod)
    return mod


S = load_sync()


def http_date_for(ed: str) -> str:
    """DocumentDate у форматі, який повертає портал для звичайної редакції."""
    import datetime as dt
    d = dt.datetime.strptime(ed, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
    import email.utils
    return email.utils.format_datetime(d, usegmt=True)


def conditional_stamp(ed: str, day_shift: int = 0) -> str:
    """Від'ємний Unix timestamp штучної дати 1100-MM-DD (як на порталі)."""
    import datetime as dt
    d = dt.datetime(1100, int(ed[4:6]), int(ed[6:8]), tzinfo=dt.timezone.utc) + dt.timedelta(days=day_shift)
    return str(int((d - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)).total_seconds()))


class Body(io.BytesIO):
    """BytesIO, що рахує читання і може обірватися посередині."""

    def __init__(self, data: bytes, fail_after: int | None = None):
        super().__init__(data)
        self.reads = 0
        self.fail_after = fail_after

    def read(self, n=-1):
        self.reads += 1
        self.max_pos = max(getattr(self, "max_pos", 0), self.tell())
        if self.fail_after is not None and self.tell() >= self.fail_after:
            raise requests.exceptions.ChunkedEncodingError("обрив з'єднання (тест)")
        data = super().read(n)
        self.max_pos = max(getattr(self, "max_pos", 0), self.tell())
        return data


def make_response(url: str, status: int = 200, body: bytes = b"", headers: dict | None = None,
                  fail_after: int | None = None, send_length: bool = True) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r.url = url
    h = CaseInsensitiveDict(headers or {})
    if send_length and "Content-Length" not in h and body:
        h["Content-Length"] = str(len(body))
    r.headers = h
    r.raw = Body(body, fail_after)
    r.encoding = "utf-8"
    return r


class FakeSession:
    """Імітація requests.Session: маршрути url → функція(headers) → Response."""

    def __init__(self):
        self.headers: dict[str, str] = {}
        self.routes: dict[str, object] = {}
        self.calls: list[tuple[str, dict]] = []
        self.ua_seen: list[str] = []

    def route(self, url: str, status: int = 200, body: bytes | str | dict = b"", headers: dict | None = None, **kw):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json", **(headers or {})}
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.routes[url] = lambda req_headers, u=url, s=status, b=body, h=headers: make_response(u, s, b, h, **kw)

    def get(self, url, headers=None, timeout=None, allow_redirects=False, stream=False):
        self.calls.append((url, dict(headers or {})))
        self.ua_seen.append(self.headers.get("User-Agent", ""))
        handler = self.routes.get(url)
        if handler is None:
            return make_response(url, 404, b"")
        return handler(headers or {})


def make_client(root: Path, session: FakeSession, budget: int = 150 * 1024 * 1024):
    sleeps: list[float] = []
    client = S.RadaHTTP(root, pause_min=5.0, pause_max=7.0, daily_budget=budget,
                        session=session, sleep=sleeps.append)
    client.sleeps = sleeps
    return client


PERELIK_HEAD = "nreg;skorocheno;nazva;rezhym;aliasy;vysnovkiv;prymitka\n"


def make_archive(rows: list[tuple[str, str, str, str]]) -> Path:
    """Тимчасовий мінімальний архів: perelik_aktiv.csv і порожня тека akty."""
    root = Path(tempfile.mkdtemp(prefix="npa41_"))
    (root / "akty").mkdir()
    (root / "dani").mkdir()
    lines = [PERELIK_HEAD] + [f"{n};{sk};{nz};{rz};;0;\n" for n, sk, nz, rz in rows]
    (root / "perelik_aktiv.csv").write_text("".join(lines), encoding="utf-8")
    return root


PODIA_TXT = "0\tРедакція\n1\tНабрання чинності\n3\tВтрата чинності\n4\tПрийняття\n6\tНова редакція\n25\tВизнання неконституційними окремих положень\n".encode("cp1251")
DOC_UPDATE_URL = "https://data.rada.gov.ua/ogd/zak/laws/data/csv/doc-update.txt"
PODIA_URL = "https://data.rada.gov.ua/ogd/zak/laws/data/csv/podia.txt"


def card_url(nreg: str, prefix: str = "laws") -> str:
    return f"https://data.rada.gov.ua/{prefix}/card/{S.encode_nreg(nreg)}.json"


def txt_url(nreg: str, ed: str | None = None, prefix: str = "laws") -> str:
    return f"https://data.rada.gov.ua/{prefix}/show/{S.encode_nreg(nreg)}" + (f"/ed{ed}" if ed else "") + ".txt"


def doc_update(rows: list[tuple[str, str, str]]) -> bytes:
    return "".join(f"{m}\t{n}\t{e}\n" for m, n, e in rows).encode("cp1251")


def act_card(nreg: str, eds: list[str], *, datred: str | None = None, edcnt: int | None = None,
             status=5, extra_eds: list[dict] | None = None, hist: list[dict] | None = None, **more) -> dict:
    items = [{"datred": e, "podid": 0, "pidstava": ""} for e in eds] + list(extra_eds or [])
    card = {"result": "ok", "nreg": nreg, "nazva": f"Тестовий акт {nreg}", "eds": items,
            "datred": datred or (eds[-1] if eds else None),
            "edcnt": edcnt if edcnt is not None else len(items), "hist": hist or [], **more}
    if status is not ...:
        card["status"] = status
    return card


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="npa41_"))
