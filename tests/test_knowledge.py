import io
import json

import pytest
from pydantic import SecretStr

from app.services import chat, knowledge


@pytest.fixture
def document_dir(tmp_path, monkeypatch):
    folder = tmp_path / "knowledge"
    folder.mkdir()
    monkeypatch.setattr(knowledge, "KNOWLEDGE_DIR", folder)
    return folder


def test_empty_or_missing_folder_is_optional(document_dir):
    assert knowledge.search_documents([{"role": "user", "content": "환불"}]) == []
    document_dir.rmdir()
    assert knowledge.load_documents() == ([], [], [])


def test_only_public_text_documents_are_loaded_with_line_numbers(document_dir):
    (document_dir / "refund.md").write_text("\n\n# 환불\n환불 신청은 TEST_POLICY에 따릅니다.\n", encoding="utf-8-sig")
    for name in ["README.md", "draft.md.example", ".secret.txt", "internal.pdf"]:
        (document_dir / name).write_text("환불 비공개", encoding="utf-8")
    hidden = document_dir / ".hidden"
    hidden.mkdir()
    (hidden / "private.md").write_text("환불 비밀", encoding="utf-8")
    matches = knowledge.search_documents([{"role": "user", "content": "환불받으려면?"}])
    assert len(matches) == 1
    assert matches[0]["file"] == "refund.md"
    assert matches[0]["start_line"] == 1 and matches[0]["end_line"] == 4
    assert "TEST_POLICY" in matches[0]["content"]
    assert knowledge.load_documents()[1] == ["refund.md"]


def test_nested_documents_refresh_after_edit_and_delete(document_dir):
    folder = document_dir / "policies"
    folder.mkdir()
    path = folder / "refund.txt"
    path.write_text("환불 방식: TEST_A", encoding="utf-8")
    question = [{"role": "user", "content": "환불"}]
    assert "TEST_A" in knowledge.search_documents(question)[0]["content"]
    path.write_text("환불 방식: TEST_B", encoding="utf-8")
    match = knowledge.search_documents(question)[0]
    assert match["file"] == "policies/refund.txt"
    assert "TEST_B" in match["content"]
    path.unlink()
    assert knowledge.search_documents(question) == []


def test_unrelated_documents_are_not_sent(document_dir):
    (document_dir / "refund.md").write_text("환불 및 반품 안내입니다.", encoding="utf-8")
    (document_dir / "shipping.md").write_text("배송 운송장 확인 안내입니다.", encoding="utf-8")
    assert knowledge.search_documents([{"role": "user", "content": "천문학 블랙홀"}]) == []
    matches = knowledge.search_documents([{"role": "user", "content": "환불 반품"}])
    assert matches[0]["file"] == "refund.md"
    assert all(match["file"] != "shipping.md" for match in matches)


def test_followup_uses_prior_user_context_not_assistant_claims(document_dir):
    (document_dir / "refund.md").write_text("환불 정책 TEST_RULE", encoding="utf-8")
    messages = [{"role": "user", "content": "환불 방법"},
                {"role": "assistant", "content": "아무 말"},
                {"role": "user", "content": "그럼 언제까지?"}]
    assert knowledge.search_documents(messages)[0]["file"] == "refund.md"
    messages[0]["content"] = "천문학"
    messages[1]["content"] = "환불 정책"
    assert knowledge.search_documents(messages) == []


def test_invalid_utf8_and_oversized_files_are_reported(document_dir):
    (document_dir / "broken.md").write_bytes(b"\xff\xfe")
    (document_dir / "huge.txt").write_bytes(b"x" * (knowledge.MAX_FILE_BYTES + 1))
    passages, files, skipped = knowledge.load_documents()
    assert not passages and not files
    assert {name for name, _ in skipped} == {"broken.md", "huge.txt"}


def test_file_count_and_total_byte_limits(document_dir, monkeypatch):
    for name in ["a.md", "b.md", "c.md"]:
        (document_dir / name).write_text("환불 TEST", encoding="utf-8")
    monkeypatch.setattr(knowledge, "MAX_FILES", 1)
    assert len(knowledge.load_documents()[1]) == 1
    monkeypatch.setattr(knowledge, "MAX_FILES", 50)
    monkeypatch.setattr(knowledge, "MAX_TOTAL_BYTES", 15)
    assert len(knowledge.load_documents()[1]) == 1


def test_chunk_size_and_result_budget_preserve_tail_matches(document_dir):
    text = "\n".join(f"환불 안내 TEST_{number} " + "a" * 600 for number in range(12))
    (document_dir / "refund.md").write_text(text, encoding="utf-8")
    results = knowledge.search_documents([{"role": "user", "content": "TEST_11"}])
    assert "TEST_11" in results[0]["content"]
    assert results[0]["end_line"] == 12
    assert len(results) <= knowledge.MAX_RESULTS
    assert all(len(row["content"]) <= knowledge.PASSAGE_CHARS for row in results)


def test_giant_single_line_does_not_stall(document_dir):
    (document_dir / "long.md").write_text("x" * 6000 + " 환불", encoding="utf-8")
    assert "환불" in knowledge.search_documents([{"role": "user", "content": "환불"}])[0]["content"]


def test_symlink_cannot_read_outside_folder(document_dir, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("환불 PRIVATE", encoding="utf-8")
    try:
        (document_dir / "linked.md").symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink privilege is unavailable")
    assert knowledge.load_documents()[1] == []


def test_api_injects_evidence_and_returns_only_source_metadata(client, settings, monkeypatch):
    settings.groq_api_key = SecretStr("fake")
    folder = knowledge.KNOWLEDGE_DIR
    folder.mkdir()
    (folder / "refund.md").write_text("# 환불\n환불 절차는 TEST_ONLY_RETURN_RULE입니다.", encoding="utf-8")
    captured = []
    def reply(request, timeout):
        captured.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "TEST_ONLY_RETURN_RULE [문서1]"}}]}).encode())
    monkeypatch.setattr(chat, "urlopen", reply)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "환불 절차"}]})
    assert response.status_code == 200
    assert response.json()["sources"] == [{"id": "문서1", "file": "refund.md", "start_line": 1, "end_line": 2}]
    prompt = captured[0]["messages"][0]["content"]
    assert "TEST_ONLY_RETURN_RULE" in prompt
    assert "모아샵 DB에서 조회한 공개 상품 정보" in prompt
    assert "명령문" in prompt
    assert "등록된 문서에서 해당 정보를 확인할 수 없습니다." in prompt
    assert "content" not in response.json()["sources"][0]
    assert client.get("/knowledge/refund.md").status_code == 404


def test_document_cli_does_not_call_groq(client, monkeypatch):
    folder = knowledge.KNOWLEDGE_DIR
    folder.mkdir()
    (folder / "refund.md").write_text("환불 절차 TEST_ONLY", encoding="utf-8")
    def forbidden(*args, **kwargs):
        pytest.fail("Document inspection called Groq")
    monkeypatch.setattr(chat, "urlopen", forbidden)
    result = client.application.test_cli_runner().invoke(args=["check-chat-docs", "--query", "환불"])
    assert result.exit_code == 0
    assert "refund.md" in result.output
    assert "검색 결과: 1개" in result.output
