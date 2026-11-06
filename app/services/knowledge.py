"""Bounded local UTF-8 document search. No embeddings or external calls."""
import re
import unicodedata
from dataclasses import dataclass

from app.core.config import PROJECT_ROOT


KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
MAX_FILE_BYTES = 128 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_FILES = 50
PASSAGE_CHARS = 1200
MAX_RESULTS = 4
STOP_WORDS = {"알려줘", "알려주세요", "해주세요", "해줘", "궁금해", "모아샵", "우리", "그거", "이거"}


@dataclass(frozen=True)
class Passage:
    file: str
    start_line: int
    end_line: int
    content: str


def split_passages(name, text):
    """Preserve line references and overlap neighboring policy sentences."""
    parts = [(number, line[offset:offset + PASSAGE_CHARS])
             for number, line in enumerate(text.splitlines(), 1)
             for offset in range(0, max(len(line), 1), PASSAGE_CHARS)]
    start = 0
    while start < len(parts):
        end, size = start, 0
        while end < len(parts) and size + len(parts[end][1]) + 1 <= PASSAGE_CHARS + 1:
            size += len(parts[end][1]) + 1
            end += 1
        body = "\n".join(line for _, line in parts[start:end]).strip()
        if body:
            yield Passage(name, parts[start][0], parts[end - 1][0], body)
        start = max(start + 1, end - 2) if end < len(parts) else end


def load_documents():
    """Only dedicated knowledge files; exclude hidden paths, README and symlinks."""
    if not KNOWLEDGE_DIR.is_dir() or KNOWLEDGE_DIR.is_symlink():
        return [], [], []
    root = KNOWLEDGE_DIR.resolve()
    passages, loaded, skipped = [], [], []
    total = 0
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        relative = path.relative_to(KNOWLEDGE_DIR)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in {".md", ".txt"} or path.name.casefold() == "readme.md":
            continue
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            continue
        if not path.is_file() or not path.resolve().is_relative_to(root):
            continue
        name = relative.as_posix()
        if len(loaded) >= MAX_FILES:
            skipped.append((name, "파일 개수 제한"))
            continue
        try:
            with path.open("rb") as source:
                raw = source.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES or total + len(raw) > MAX_TOTAL_BYTES:
                skipped.append((name, "파일 또는 전체 용량 제한"))
                continue
            text = raw.decode("utf-8-sig")
        except (OSError, UnicodeError):
            skipped.append((name, "UTF-8 읽기 실패"))
            continue
        if not text.strip():
            continue
        total += len(raw)
        loaded.append(name)
        passages.extend(split_passages(name, text))
    return passages, loaded, skipped


def normalized(text):
    return unicodedata.normalize("NFKC", text).casefold()


def terms(query):
    return {word for word in re.findall(r"[a-z0-9가-힣]+", normalized(query))
            if len(word) >= 2 and word not in STOP_WORDS}


def score(passage, query):
    text = normalized(passage.file + "\n" + passage.content)
    value = 0.0
    for word in terms(query):
        if word in text:
            value += 4.0
        elif re.search(r"[가-힣]", word):
            pairs = {word[i:i + 2] for i in range(len(word) - 1)}
            value += sum(pair in text for pair in pairs) / max(len(pairs), 1)
    return value


def search_documents(messages):
    passages, _, _ = load_documents()
    questions = [message["content"] for message in messages if message["role"] == "user"]
    if not questions:
        return []
    query = questions[-1]
    previous = " ".join(questions[-3:-1])[-1000:]
    followup = bool(previous and re.search(r"그럼|그러면|그건|그거|언제|얼마|며칠|이 경우|그 경우", query))
    ranked = []
    for passage in passages:
        relevance = score(passage, query)
        context = score(passage, previous) if previous else 0
        if relevance > 0 or ((not terms(query) or followup) and context > 0):
            ranked.append((relevance + context * .25, passage))
    ranked.sort(key=lambda item: (-item[0], item[1].file, item[1].start_line))
    results = []
    for _, passage in ranked:
        if any(row["file"] == passage.file and row["start_line"] <= passage.end_line
               and passage.start_line <= row["end_line"] for row in results):
            continue
        results.append({"id": f"문서{len(results) + 1}", "file": passage.file,
                        "start_line": passage.start_line, "end_line": passage.end_line,
                        "content": passage.content})
        if len(results) == MAX_RESULTS:
            break
    return results
