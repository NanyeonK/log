#!/usr/bin/env python3
"""publish_from_life.py — second_brain life-log를 media_blog 콘텐츠 컬렉션으로 발행.

소스 (SynologyDrive-second_brain/00_wiki/life):
  album-log/*.md            -> src/content/music/
  watch-log/*.md            -> src/content/films/
  reading-log/**/*.md       -> src/content/books/   (book-log 하위 포함)

frontmatter에 `publish: true` 인 노트만 변환·복사한다.
`cover:` 필드(노트 기준 상대경로 또는 절대경로)가 있으면 이미지를
public/covers/ 로 복사하고 frontmatter를 블로그 경로로 재작성한다.

사용:
  python3 scripts/publish_from_life.py                 # 기본 소스에서 발행
  python3 scripts/publish_from_life.py --dry-run       # 쓰기 없이 계획만 출력
  python3 scripts/publish_from_life.py --source DIR    # 소스 루트 교체(테스트용)
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

BLOG_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path.home() / (
    "Library/CloudStorage/SynologyDrive-second_brain/00_wiki/life"
)

# 소스 하위 디렉토리 -> (블로그 컬렉션, 소스 type 값)
MAPPING = {
    "album-log": ("music", "album-log"),
    "watch-log": ("films", "watch-log"),
    "reading-log": ("books", "book-log"),
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}
FALLBACK_COVER = {
    "music": "/covers/placeholder-music.svg",
    "films": "/covers/placeholder-film.svg",
    "books": "/covers/placeholder-book.svg",
}


# ---------------------------------------------------------------- frontmatter
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """frontmatter dict + body 반환. PyYAML 있으면 사용, 없으면 미니 파서."""
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end():]
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            data = {}
        return data, body
    except ImportError:
        return _mini_yaml(raw), body


def _mini_yaml(raw: str) -> dict:
    """의존성 없는 최소 YAML 파서(평면 key: value + 인라인/블록 리스트)."""
    data: dict = {}
    key = None
    for line in raw.splitlines():
        if re.match(r"^\s*-\s+", line) and key is not None:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(_coerce(re.sub(r"^\s*-\s+", "", line).strip()))
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            data[key] = None  # 블록 리스트 시작이거나 빈 값
        elif val.startswith("[") and val.endswith("]"):
            items = [v.strip() for v in val[1:-1].split(",") if v.strip()]
            data[key] = [_coerce(v) for v in items]
        else:
            data[key] = _coerce(val)
    return data


def _coerce(val: str):
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        return val[1:-1]
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if re.fullmatch(r"-?\d+\.\d+", val):
        return float(val)
    return val


# ---------------------------------------------------------------- transforms
def parse_rating(val) -> float | None:
    """'8/10' | '/10' | 8 | 8.5 -> 0-10 float 또는 None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*/\s*10$", s)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1))
    return None  # '/10' (미기입) 등


def parse_date(fm: dict, collection: str, path: Path) -> str:
    """감상일 추출. album=listened 마지막 날짜, film=watched, book=finished>started."""
    candidates: list[str] = []
    if collection == "music":
        raw = str(fm.get("listened") or "")
        candidates = [p.strip() for p in raw.split("/") if p.strip()]
        # 'YYYY-MM-DD / YYYY-MM-DD' -> 마지막 조각이 종료일
        candidates = candidates[::-1]
    elif collection == "films":
        candidates = [str(fm.get("watched") or "")]
    else:
        candidates = [str(fm.get("finished") or ""), str(fm.get("started") or "")]
    for c in candidates:
        c = c.strip().strip("'\"")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c):
            return c
    # 폴백: 파일 수정일
    d = date.fromtimestamp(path.stat().st_mtime).isoformat()
    print(f"    [warn] {path.name}: 감상일 없음 -> 파일 수정일 {d} 사용")
    return d


def extract_tracks(body: str) -> list[str]:
    """'## Tracks' 섹션의 '### 1. Title (9:22)' 헤딩 -> 'Title (9:22)' 리스트."""
    m = re.search(r"^## Tracks\s*$(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    tracks = []
    for h in re.finditer(r"^###\s+(?:\d+[.)]\s*)?(.+)$", m.group(1), re.MULTILINE):
        tracks.append(h.group(1).strip())
    return tracks


def clean_body(body: str) -> str:
    """내부 위키 전용 요소 제거: Cascade 섹션, [[wikilink]] 평문화."""
    body = re.sub(r"^## Cascade\s*$(.*?)(?=^## |\Z)", "", body, flags=re.MULTILINE | re.DOTALL)
    body = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", body)  # [[x|y]] -> y
    body = re.sub(r"\[\[([^\]]+)\]\]", r"\1", body)  # [[x]] -> x
    return body.strip() + "\n"


def resolve_cover(fm: dict, note: Path, slug: str, collection: str, dry: bool) -> str:
    """cover 필드 처리: 이미지를 public/covers/로 복사하고 블로그 경로 반환."""
    raw = fm.get("cover")
    if not raw or not isinstance(raw, str):
        return FALLBACK_COVER[collection]
    raw = raw.strip()
    if raw.startswith("/covers/"):
        return raw  # 이미 블로그 경로
    src = Path(raw).expanduser()
    if not src.is_absolute():
        src = (note.parent / raw).resolve()
    if not src.exists() or src.suffix.lower() not in IMAGE_EXTS:
        print(f"    [warn] {note.name}: cover '{raw}' 를 찾지 못함 -> placeholder 사용")
        return FALLBACK_COVER[collection]
    dest = BLOG_ROOT / "public" / "covers" / f"{slug}{src.suffix.lower()}"
    if not dry:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return f"/covers/{dest.name}"


# ---------------------------------------------------------------- yaml output
def _q(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def dump_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if v is None:
            continue
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            v = int(v) if isinstance(v, float) and v.is_integer() else v
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                continue
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {_q(item)}")
        else:
            lines.append(f"{k}: {_q(v)}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------- conversion
def convert(note: Path, collection: str, dry: bool) -> bool:
    text = note.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if fm.get("publish") is not True:
        return False

    slug = re.sub(r"[^a-z0-9가-힣-]+", "-", note.stem.lower()).strip("-") or note.stem
    out: dict = {"title": str(fm.get("title") or note.stem)}

    if collection == "music":
        out["artist"] = str(fm.get("artist") or "Unknown")
        if fm.get("label"):
            out["label"] = str(fm["label"])
        tracks = fm.get("tracks") or extract_tracks(body)
        if tracks:
            out["tracks"] = [str(t) for t in tracks]
    elif collection == "films":
        out["director"] = str(fm.get("director") or "Unknown")
        if fm.get("cast"):
            out["cast"] = [str(c) for c in fm["cast"]]
    else:
        out["author"] = str(fm.get("author") or "Unknown")
        if fm.get("publisher"):
            out["publisher"] = str(fm["publisher"])
        if isinstance(fm.get("pages"), int):
            out["pages"] = fm["pages"]

    if isinstance(fm.get("year"), int):
        out["year"] = fm["year"]
    genre = fm.get("genre")
    if genre:
        out["genre"] = [str(g) for g in genre] if isinstance(genre, list) else str(genre)
    out["cover"] = resolve_cover(fm, note, slug, collection, dry)
    rating = parse_rating(fm.get("rating"))
    if rating is not None:
        out["rating"] = rating
    out["date"] = parse_date(fm, collection, note)
    out["publish"] = True

    dest = BLOG_ROOT / "src" / "content" / collection / f"{slug}.md"
    content = dump_frontmatter(out) + "\n\n" + clean_body(body)
    print(f"  {'[dry] ' if dry else ''}{note.name} -> {dest.relative_to(BLOG_ROOT)}")
    if not dry:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help=f"life-log 루트 (기본: {DEFAULT_SOURCE})")
    ap.add_argument("--dry-run", action="store_true", help="쓰기 없이 계획만 출력")
    args = ap.parse_args()

    root: Path = args.source.expanduser()
    if not root.is_dir():
        print(f"[error] 소스 루트를 읽을 수 없음: {root}", file=sys.stderr)
        print("        (CloudStorage 미마운트이거나 권한 문제일 수 있음)", file=sys.stderr)
        return 1

    total = 0
    for subdir, (collection, _) in MAPPING.items():
        src_dir = root / subdir
        if not src_dir.is_dir():
            print(f"[skip] {src_dir} 없음")
            continue
        print(f"[{subdir}] -> src/content/{collection}/")
        for note in sorted(src_dir.rglob("*.md")):
            if note.name.startswith("_") or "_archive" in str(note.parent):
                continue
            try:
                if convert(note, collection, args.dry_run):
                    total += 1
            except Exception as exc:  # 한 노트 실패가 전체를 막지 않게
                print(f"    [error] {note}: {exc}", file=sys.stderr)

    print(f"\n{'[dry-run] ' if args.dry_run else ''}발행 대상 {total}건 처리 완료")
    if total:
        print("다음 단계: npm run build 로 사이트 재생성")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
