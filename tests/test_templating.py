from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("jinja2", reason="Templating tests require jinja2 to be installed.")

from rsgi import Response, TemplateEngine, TemplateResponse


def test_template_engine_renders_from_directory(tmp_path: Path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "hello.html").write_text("Hello {{ name }}!")

    engine = TemplateEngine.from_directory(templates)
    rendered = engine.render("hello.html", {"name": "RSGI"})
    assert rendered == "Hello RSGI!"


def test_template_response_sets_content_type(tmp_path: Path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page.html").write_text("<title>{{ title }}</title>")

    engine = TemplateEngine.from_directory(templates)
    res = TemplateResponse("page.html", {"title": "Home"}, engine=engine)

    assert res.status == 200
    assert res.body == b"<title>Home</title>"
    assert ("content-type", "text/html; charset=utf-8") in res.headers


def test_template_response_raises_for_missing_template(tmp_path: Path):
    engine = TemplateEngine.from_directory(tmp_path)
    with pytest.raises(FileNotFoundError):
        engine.render("missing.html", {})
