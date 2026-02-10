from __future__ import annotations

from rsgi import Response


def test_text_and_html_helpers():
    text_res = Response.text("hello")
    assert text_res.body == b"hello"
    assert ("content-type", "text/plain; charset=utf-8") in text_res.headers

    html_res = Response.html("<p>ok</p>")
    assert html_res.body == b"<p>ok</p>"
    assert ("content-type", "text/html; charset=utf-8") in html_res.headers


def test_json_and_bytes_helpers():
    res = Response.json({"a": 1})
    assert res.body == b'{"a":1}'
    assert ("content-type", "application/json; charset=utf-8") in res.headers

    data = b"\x00\x01"
    bytes_res = Response.bytes(data, content_type="application/data")
    assert bytes_res.body is data
    assert ("content-type", "application/data") in bytes_res.headers


def test_render_with_default_template_engine():
    res = Response.render("<h1>${title}</h1>", {"title": "Hello"})
    assert res.body == b"<h1>Hello</h1>"


def test_render_with_callable_template():
    def template(ctx):
        return f"<p>{ctx['msg']}</p>"

    res = Response.render(template, {"msg": "Hi"})
    assert res.body == b"<p>Hi</p>"
