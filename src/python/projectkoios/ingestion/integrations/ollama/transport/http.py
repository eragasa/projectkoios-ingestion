from __future__ import annotations

import http.client
import ipaddress
from urllib.parse import urlsplit

from projectkoios.ingestion.integrations.ollama.base import (
    OllamaHttpResponse,
    OllamaMultimodalConfigurationError,
    OllamaTransport,
    OllamaTransportError,
    OllamaTransportFailureKind,
)

_READ_CHUNK_BYTES = 65_536


class LoopbackOllamaHttpTransport(OllamaTransport):
    """Direct local HTTP transport with no proxy, redirect, or auth support."""

    def request(
        self,
        *,
        endpoint: str,
        method: str,
        path: str,
        body: bytes | None,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_response_bytes: int,
    ) -> OllamaHttpResponse:
        normalized = normalize_ollama_endpoint(endpoint)
        parsed = urlsplit(normalized)
        if method not in ("GET", "POST"):
            raise OllamaTransportError(
                OllamaTransportFailureKind.PROTOCOL,
                "unsupported Ollama HTTP method",
            )
        if path not in (
            "/api/version",
            "/api/tags",
            "/api/show",
            "/api/chat",
        ):
            raise OllamaTransportError(
                OllamaTransportFailureKind.PROTOCOL,
                "unsupported Ollama API path",
            )
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        hostname = parsed.hostname
        if hostname is None:
            raise OllamaTransportError(
                OllamaTransportFailureKind.PROTOCOL,
                "normalized Ollama endpoint has no host",
            )
        connection = http.client.HTTPConnection(
            hostname,
            parsed.port,
            timeout=float(connect_timeout_seconds),
        )
        try:
            connection.connect()
            if connection.sock is None:
                raise OllamaTransportError(
                    OllamaTransportFailureKind.NETWORK,
                    "Ollama connection did not create a socket",
                )
            peer_host = connection.sock.getpeername()[0]
            if not ipaddress.ip_address(peer_host).is_loopback:
                raise OllamaTransportError(
                    OllamaTransportFailureKind.PROTOCOL,
                    "Ollama connection peer is not loopback",
                )
            connection.sock.settimeout(float(read_timeout_seconds))
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            declared = response.getheader("Content-Length")
            if declared is not None:
                try:
                    declared_length = int(declared)
                except ValueError as error:
                    raise OllamaTransportError(
                        OllamaTransportFailureKind.PROTOCOL,
                        "Ollama response has invalid Content-Length",
                    ) from error
                if declared_length < 0 or declared_length > max_response_bytes:
                    raise OllamaTransportError(
                        OllamaTransportFailureKind.RESPONSE_LIMIT,
                        "Ollama response exceeds configured byte limit",
                    )
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_response_bytes:
                    raise OllamaTransportError(
                        OllamaTransportFailureKind.RESPONSE_LIMIT,
                        "Ollama response exceeds configured byte limit",
                    )
                chunks.append(chunk)
            return OllamaHttpResponse(
                status_code=response.status,
                content_type=response.getheader("Content-Type", ""),
                body=b"".join(chunks),
            )
        except TimeoutError as error:
            raise OllamaTransportError(
                OllamaTransportFailureKind.TIMEOUT,
                "Ollama request timed out",
            ) from error
        except OllamaTransportError:
            raise
        except (OSError, http.client.HTTPException) as error:
            raise OllamaTransportError(
                OllamaTransportFailureKind.NETWORK,
                "Ollama local HTTP request failed",
            ) from error
        finally:
            connection.close()


def normalize_ollama_endpoint(endpoint: str) -> str:
    """Validate and privacy-normalize an explicit loopback HTTP endpoint."""
    if not isinstance(endpoint, str):
        raise TypeError("endpoint must be a string")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http":
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint must use loopback HTTP"
        )
    if parsed.username is not None or parsed.password is not None:
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint must not contain credentials"
        )
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint must not contain a path, query, or fragment"
        )
    hostname = parsed.hostname
    if hostname is None:
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint must contain a host"
        )
    canonical_host: str
    if hostname.lower() == "localhost":
        canonical_host = "localhost"
    else:
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as error:
            raise OllamaMultimodalConfigurationError(
                "Ollama endpoint host must be explicit loopback"
            ) from error
        if not address.is_loopback:
            raise OllamaMultimodalConfigurationError(
                "Ollama endpoint host must be explicit loopback"
            )
        canonical_host = (
            f"[{address.compressed}]"
            if address.version == 6
            else address.compressed
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint port is invalid"
        ) from error
    if port is None:
        port = 80
    if not 1 <= port <= 65_535:
        raise OllamaMultimodalConfigurationError(
            "Ollama endpoint port is invalid"
        )
    return f"http://{canonical_host}:{port}"
