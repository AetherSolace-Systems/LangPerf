"""Decode OTLP trace payloads (protobuf or JSON) into plain Python dicts.

We normalize into a shape that mirrors OTel's semantic model closely:

    {
        "resource": { "attrs": {...} },
        "spans": [
            {
                "trace_id": "hex",
                "span_id": "hex",
                "parent_span_id": "hex" | None,
                "name": str,
                "kind": str,                      # OTel SpanKind name
                "start_time_unix_nano": int,
                "end_time_unix_nano": int,
                "attributes": {...},              # flattened str->primitive
                "events": [...],
                "status": {"code": str, "message": str},
                "scope": {"name": str, "version": str | None},
            },
            ...
        ]
    }

The attribute bag merges span attributes only (not resource) per span dict; resource
attributes are carried separately so the receiver can apply them uniformly to each span.
"""

from __future__ import annotations

from typing import Any

from google.protobuf.json_format import Parse
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan


_SPAN_KIND_NAMES = {
    0: "UNSPECIFIED",
    1: "INTERNAL",
    2: "SERVER",
    3: "CLIENT",
    4: "PRODUCER",
    5: "CONSUMER",
}

_STATUS_CODE_NAMES = {
    0: "UNSET",
    1: "OK",
    2: "ERROR",
}


def decode(body: bytes, content_type: str) -> list[dict[str, Any]]:
    """Decode a raw OTLP body into a list of resource-grouped span bundles."""
    req = ExportTraceServiceRequest()
    if "json" in content_type.lower():
        Parse(body.decode("utf-8"), req)
    else:
        req.ParseFromString(body)

    bundles: list[dict[str, Any]] = []
    for rs in req.resource_spans:
        resource_attrs = _kv_list_to_dict(rs.resource.attributes)
        spans_out: list[dict[str, Any]] = []
        for ss in rs.scope_spans:
            scope = {
                "name": ss.scope.name or None,
                "version": ss.scope.version or None,
            }
            for span in ss.spans:
                spans_out.append(_convert_span(span, scope))
        bundles.append({"resource": {"attrs": resource_attrs}, "spans": spans_out})
    return bundles


def _convert_span(span: PbSpan, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_id": span.trace_id.hex() if span.trace_id else None,
        "span_id": span.span_id.hex() if span.span_id else None,
        "parent_span_id": span.parent_span_id.hex() if span.parent_span_id else None,
        "name": span.name,
        "kind": _SPAN_KIND_NAMES.get(span.kind, "UNSPECIFIED"),
        "start_time_unix_nano": span.start_time_unix_nano,
        "end_time_unix_nano": span.end_time_unix_nano,
        "attributes": _kv_list_to_dict(span.attributes),
        "events": [
            {
                "name": ev.name,
                "time_unix_nano": ev.time_unix_nano,
                "attributes": _kv_list_to_dict(ev.attributes),
            }
            for ev in span.events
        ],
        "status": {
            "code": _STATUS_CODE_NAMES.get(span.status.code, "UNSET"),
            "message": span.status.message or "",
        },
        "scope": scope,
    }


def _kv_list_to_dict(kvs) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kv in kvs:
        out[kv.key] = _unwrap_any_value(kv.value)
    return out


def _unwrap_any_value(v) -> Any:
    # AnyValue has one_of: string_value, bool_value, int_value, double_value, array_value, kvlist_value, bytes_value
    which = v.WhichOneof("value")
    if which is None:
        return None
    if which == "string_value":
        return v.string_value
    if which == "bool_value":
        return v.bool_value
    if which == "int_value":
        return v.int_value
    if which == "double_value":
        return v.double_value
    if which == "bytes_value":
        return v.bytes_value
    if which == "array_value":
        return [_unwrap_any_value(av) for av in v.array_value.values]
    if which == "kvlist_value":
        return {kv.key: _unwrap_any_value(kv.value) for kv in v.kvlist_value.values}
    return None
