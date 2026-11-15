"""Incomplete web-graph downloads must not become cached absence findings."""

from __future__ import annotations

import gzip
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import commoncrawl_graph as ccg  # noqa: E402

RELEASE = "cc-main-2026-jul-aug-sep"
RANKING = "1\t0.4\t2\t0.2\tcom.example\t3"


class StreamResponse:
    def __init__(self, chunks, failure=None, status=200):
        self.chunks = chunks
        self.failure = failure
        self.status_code = status
        self.closed = False
        self.headers = {}
        response = self

        class Stream(io.BytesIO):
            def read(self, size=-1):
                chunk = super().read(size)
                if not chunk and response.failure:
                    raise response.failure
                return chunk

        self.raw = Stream(b"".join(chunks))

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ccg.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self.chunks
        if self.failure:
            raise self.failure

    def close(self):
        self.closed = True
        self.raw.close()


@pytest.fixture
def lookup(monkeypatch, tmp_path):
    responses = []
    writes = []
    monkeypatch.setattr(ccg, "get_cache_dir", lambda: str(tmp_path))

    def get(url, **kwargs):
        assert kwargs["stream"] is True
        return responses.pop(0)

    monkeypatch.setattr(ccg.requests, "get", get)
    monkeypatch.setattr(ccg, "_save_cache", lambda *args: writes.append(args))
    return responses, writes


@pytest.mark.parametrize("kind", ["timeout", "corrupt", "truncated", "http"])
def test_failed_rank_scan_is_an_error_and_is_not_cached(lookup, kind):
    responses, writes = lookup
    payload = gzip.compress(b"1\t0.4\t2\t0.2\torg.other\t3\n")
    cases = {
        "timeout": StreamResponse([], ccg.requests.exceptions.Timeout("timed out")),
        "corrupt": StreamResponse([b"not a gzip graph"]),
        "truncated": StreamResponse([payload[:-8]]),
        "http": StreamResponse([], status=503),
    }
    response = cases[kind]
    responses.extend([response, StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert result["error"]
    assert result["data"] is None
    assert writes == []
    assert response.closed


def test_failed_vertex_scan_does_not_establish_absence(lookup):
    responses, writes = lookup
    rank = StreamResponse([gzip.compress(b"1\t0.4\t2\t0.2\torg.other\t3\n")])
    vertex = StreamResponse([], ccg.requests.exceptions.Timeout("timed out"))
    responses.extend([rank, vertex])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert writes == []
    assert rank.closed and vertex.closed


@pytest.mark.parametrize("trailing_newline", [False, True])
def test_exact_ranking_row_and_zero_value_are_positive_evidence(lookup, trailing_newline):
    responses, writes = lookup
    row = RANKING.replace("0.2", "0") + ("\n" if trailing_newline else "")
    response = StreamResponse([gzip.compress(row.encode())])
    responses.extend([response, StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "success"
    assert result["data"]["in_rankings"] is True
    assert result["data"]["in_crawl"] is True
    assert result["data"]["pagerank"] == 0.0
    assert len(writes) == 1
    assert response.closed


def test_complete_negative_lookup_is_still_reported_and_cached(lookup):
    responses, writes = lookup
    rank = StreamResponse([gzip.compress(b"1\t0.4\t2\t0.2\torg.other\t3\n")])
    vertex = StreamResponse([gzip.compress(b"1\torg.other\n")])
    responses.extend([rank, vertex])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "success"
    assert result["data"]["in_crawl"] is False
    assert result["data"]["in_rankings"] is False
    assert len(writes) == 1
    assert rank.closed and vertex.closed


@pytest.mark.parametrize("stage", ["rank", "vertex"])
def test_empty_http_entity_is_not_an_empty_graph(lookup, stage):
    responses, writes = lookup
    if stage == "vertex":
        responses.append(StreamResponse([gzip.compress(b"")]))
    empty = StreamResponse([])
    responses.extend([empty, StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert writes == []
    assert empty.closed


def test_valid_empty_gzip_is_a_complete_negative_lookup(lookup):
    responses, writes = lookup
    responses.extend([StreamResponse([gzip.compress(b"")]) for _ in range(2)])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "success"
    assert result["data"]["in_crawl"] is False
    assert result["metadata"]["lookup_complete"] is True
    assert len(writes) == 1


@pytest.mark.parametrize("malformed", ["com.example", "1\t0.4\t2\t0.2\tcom.example"])
def test_malformed_target_row_cannot_end_the_rank_scan(lookup, malformed):
    responses, writes = lookup
    payload = gzip.compress((malformed + "\n" + RANKING + "\n").encode())
    responses.extend([StreamResponse([payload]), StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert writes == []


def test_malformed_vertex_row_cannot_establish_presence(lookup):
    responses, writes = lookup
    responses.extend([
        StreamResponse([gzip.compress(b"")]),
        StreamResponse([gzip.compress(b"com.example\n")]),
    ])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert writes == []


def test_matching_row_stops_before_downloading_the_rest(lookup):
    responses, writes = lookup
    response = StreamResponse(
        [gzip.compress((RANKING + "\n").encode())],
        ccg.requests.exceptions.Timeout("should not read past the exact row"),
    )
    responses.append(response)
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "success"
    assert result["data"]["pagerank"] == 0.2
    assert len(writes) == 1
    assert response.closed


def test_unrelated_domain_suffixes_do_not_stop_the_rank_search(lookup):
    responses, _ = lookup
    rows = [RANKING.replace("com.example", f"org{i}.com.example") for i in range(5)]
    rows.append(RANKING)
    response = StreamResponse([gzip.compress(("\n".join(rows) + "\n").encode())])
    responses.extend([response, StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["data"]["pagerank"] == 0.2


def test_legacy_negative_cache_is_not_treated_as_a_complete_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(ccg, "get_cache_dir", lambda: str(tmp_path))
    cached = {
        "status": "success", "data": {"in_crawl": False, "in_rankings": False},
        "metadata": {"cached_at": ccg.time.time()},
    }
    path = Path(ccg._get_cache_path("example.com", RELEASE, "combined"))
    path.write_text(json.dumps(cached))
    assert ccg._is_cached("example.com", RELEASE) is None


def test_completed_lookup_cache_is_reusable(monkeypatch, tmp_path):
    monkeypatch.setattr(ccg, "get_cache_dir", lambda: str(tmp_path))
    cached = {
        "status": "success", "data": {"in_crawl": False, "in_rankings": False},
        "metadata": {"cached_at": ccg.time.time(), "lookup_complete": True},
    }
    path = Path(ccg._get_cache_path("example.com", RELEASE, "combined"))
    path.write_text(json.dumps(cached))
    assert ccg._is_cached("example.com", RELEASE) == cached


def test_concatenated_gzip_members_include_later_domain_rows(lookup):
    responses, _ = lookup
    members = gzip.compress(b"1\t0.4\t2\t0.2\torg.other\t3\n")
    members += gzip.compress((RANKING + "\n").encode())
    responses.extend([StreamResponse([members]), StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "success"
    assert result["data"]["pagerank"] == 0.2


def test_download_cap_does_not_become_an_absence_finding(monkeypatch, lookup):
    responses, writes = lookup
    payload = gzip.compress(b"1\t0.4\t2\t0.2\torg.other\t3\n")
    monkeypatch.setattr(ccg, "MAX_COMPRESSED_BYTES", len(payload) - 1, raising=False)
    response = StreamResponse([payload])
    responses.extend([response, StreamResponse([gzip.compress(b"")])])
    result = ccg.get_domain_metrics("example.com", release=RELEASE)
    assert result["status"] == "error"
    assert "limit" in result["error"]
    assert writes == []
    assert response.closed


@pytest.mark.parametrize("json_output", [False, True])
def test_incomplete_lookup_has_a_failing_cli_exit(monkeypatch, capsys, json_output):
    monkeypatch.setattr(ccg, "get_domain_metrics", lambda **kw: {
        "status": "error", "data": None, "error": "lookup was incomplete", "metadata": {},
    })
    monkeypatch.setattr(sys, "argv", ["commoncrawl_graph.py", "example.com"]
                        + (["--json"] if json_output else []))
    assert ccg.main() == 1
    output = capsys.readouterr()
    if json_output:
        assert json.loads(output.out)["status"] == "error"
    else:
        assert "lookup was incomplete" in output.err


@pytest.mark.parametrize("gzip_content_encoding,layers", [(False, 1), (True, 1), (True, 2)])
def test_lookup_reads_a_real_http_gzip_response(monkeypatch, tmp_path, gzip_content_encoding, layers):
    payload = gzip.compress((RANKING + "\n").encode())
    if layers == 2:
        payload = gzip.compress(payload)
    requested_encodings = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested_encodings.append(self.headers.get("Accept-Encoding"))
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Length", str(len(payload)))
            if gzip_content_encoding:
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    worker.start()
    try:
        local_url = f"http://127.0.0.1:{server.server_port}/ranks.txt.gz"
        monkeypatch.setattr(ccg, "_graph_file_url", lambda *args: local_url)
        monkeypatch.setattr(ccg, "get_cache_dir", lambda: str(tmp_path))
        result = ccg.get_domain_metrics("example.com", release=RELEASE)
        assert result["status"] == "success"
        assert result["data"]["pagerank"] == 0.2
        assert result["data"]["in_rankings"] is True
        assert ccg._is_cached("example.com", RELEASE)["data"] == result["data"]
        # The raw reader supports the gzip graph representation, so it must
        # not advertise unrelated HTTP codecs such as deflate, br, or zstd.
        assert requested_encodings == ["identity"]
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
