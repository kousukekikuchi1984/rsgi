from __future__ import annotations

import datetime as dt

import pytest

from rsgi import JSONResponse, MsgPackResponse, ORJSONResponse, UJSONResponse


def test_json_response_serializes_dict():
    res = JSONResponse({"ok": True}, status=201, headers=[("x-test", "1")])
    assert res.status == 201
    assert res.body == b'{"ok":true}'
    assert ("content-type", "application/json; charset=utf-8") in res.headers
    assert ("x-test", "1") in res.headers


def test_json_response_supports_custom_dumps_kwargs():
    res = JSONResponse({"ts": dt.datetime(2024, 1, 1)}, dumps_kwargs={"default": str})
    assert b"2024-01-01" in res.body


def test_ujson_response_requires_dependency(monkeypatch):
    monkeypatch.setattr("rsgi.response._ujson", None, raising=False)
    with pytest.raises(ModuleNotFoundError):
        UJSONResponse({"ok": True})


def test_orjson_response_requires_dependency(monkeypatch):
    monkeypatch.setattr("rsgi.response._orjson", None, raising=False)
    with pytest.raises(ModuleNotFoundError):
        ORJSONResponse({"ok": True})


def test_ujson_response_round_trip(monkeypatch):
    ujson = pytest.importorskip("ujson")
    monkeypatch.setattr("rsgi.response._ujson", ujson, raising=False)
    res = UJSONResponse({"hello": "world"})
    assert res.body == ujson.dumps({"hello": "world"}).encode()


def test_orjson_response_round_trip(monkeypatch):
    orjson = pytest.importorskip("orjson")
    monkeypatch.setattr("rsgi.response._orjson", orjson, raising=False)
    res = ORJSONResponse({"hello": "world"})
    assert res.body == orjson.dumps({"hello": "world"})


def test_msgpack_response_requires_dependency(monkeypatch):
    monkeypatch.setattr("rsgi.response._msgpack", None, raising=False)
    with pytest.raises(ModuleNotFoundError):
        MsgPackResponse({"ok": True})


def test_msgpack_response_round_trip(monkeypatch):
    msgpack = pytest.importorskip("msgpack")
    monkeypatch.setattr("rsgi.response._msgpack", msgpack, raising=False)
    res = MsgPackResponse({"hello": "world"})
    assert res.body == msgpack.packb({"hello": "world"})
