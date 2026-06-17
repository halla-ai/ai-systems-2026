"""Tests for sample API."""

from api import greet, parse_json


def test_parse_json():
    assert parse_json("[]") == []


def test_greet():
    assert greet("world", loud=False) == "world"
