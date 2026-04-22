"""WeCom (Enterprise WeChat) channel integration.

Supports two modes:

- ``long_connection``: preferred mode for WeCom AI bots using Bot ID + Secret
  over WebSocket long connections.
- ``callback``: compatibility mode using callback URL verification and the
  classic app message APIs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import hashlib
import hmac
import logging
import mimetypes
import secrets
import struct
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.channels.base import Channel
from app.channels.message_bus import InboundMessage, InboundMessageType, MessageBus, OutboundMessage, ResolvedAttachment

logger = logging.getLogger(__name__)

_WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
_WECOM_ROBOT_UPLOAD_URL = f"{_WECOM_API_BASE}/webhook/upload_media"
_WECOM_ROBOT_SEND_URL = f"{_WECOM_API_BASE}/webhook/send"


class WecomCrypto:
    """Handle WeCom callback signature verification and AES encryption."""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        self.token = token
        self.receive_id = receive_id
        self._key = base64.b64decode(encoding_aes_key + "=")
        if len(self._key) != 32:
            raise ValueError("WeCom EncodingAESKey must decode to 32 bytes")

    @staticmethod
    def _sha1_signature(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
        return hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()

    def verify_signature(self, signature: str, timestamp: str, nonce: str, encrypted: str) -> bool:
        expected = self._sha1_signature(self.token, timestamp, nonce, encrypted)
        return hmac.compare_digest(expected, signature)

    def decrypt(self, encrypted: str) -> str:
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(self._key[:16]))
        decryptor = cipher.decryptor()
        padded = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        plain = unpadder.update(padded) + unpadder.finalize()
        msg_len = struct.unpack(">I", plain[16:20])[0]
        content = plain[20 : 20 + msg_len]
        receive_id = plain[20 + msg_len :].decode("utf-8")
        if receive_id != self.receive_id:
            raise ValueError("WeCom receive_id mismatch")
        return content.decode("utf-8")

    def decrypt_message(self, signature: str, timestamp: str, nonce: str, encrypted: str) -> str:
        if not self.verify_signature(signature, timestamp, nonce, encrypted):
            raise ValueError("Invalid WeCom callback signature")
        return self.decrypt(encrypted)

    def encrypt(self, plain_text: str) -> str:
        plain_bytes = plain_text.encode("utf-8")
        raw = secrets.token_bytes(16) + struct.pack(">I", len(plain_bytes)) + plain_bytes + self.receive_id.encode("utf-8")
        padder = padding.PKCS7(128).padder()
        padded = padder.update(raw) + padder.finalize()
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(self._key[:16]))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("utf-8")


class WecomClient:
    """Minimal WeCom application API client for callback/app mode."""

    def __init__(self, corp_id: str, agent_id: str | int, secret: str, *, timeout: float = 10.0) -> None:
        self.corp_id = corp_id
        self.agent_id = str(agent_id)
        self.secret = secret
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at = 0.0

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, params=params, json=json_body, files=files, data=data)
            response.raise_for_status()
            payload = response.json()
        if payload.get("errcode", 0) != 0:
            raise RuntimeError(f"WeCom API error {payload.get('errcode')}: {payload.get('errmsg')}")
        return payload

    async def get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        payload = await self._request_json(
            "GET",
            f"{_WECOM_API_BASE}/gettoken",
            params={"corpid": self.corp_id, "corpsecret": self.secret},
        )
        self._token = str(payload["access_token"])
        expires_in = int(payload.get("expires_in", 7200))
        self._token_expires_at = time.time() + max(60, expires_in - 120)
        return self._token

    async def _authed_request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        params = {"access_token": token}
        if extra_params:
            params.update(extra_params)
        return await self._request_json(
            method,
            f"{_WECOM_API_BASE}{path}",
            params=params,
            json_body=json_body,
            files=files,
            data=data,
        )

    async def send_text(self, *, target_kind: str, target_id: str, content: str) -> dict[str, Any]:
        payload = {
            "agentid": self.agent_id,
            "msgtype": "text",
            "text": {"content": content},
            "safe": 0,
            "enable_duplicate_check": 0,
        }
        payload[self._target_field(target_kind)] = target_id
        return await self._authed_request_json("POST", "/message/send", json_body=payload)

    async def send_markdown(self, *, target_kind: str, target_id: str, content: str) -> dict[str, Any]:
        payload = {
            "agentid": self.agent_id,
            "msgtype": "markdown",
            "markdown": {"content": content},
            "safe": 0,
            "enable_duplicate_check": 0,
        }
        payload[self._target_field(target_kind)] = target_id
        return await self._authed_request_json("POST", "/message/send", json_body=payload)

    async def upload_media(self, file_path: Path, *, media_type: str = "file") -> str:
        with open(file_path, "rb") as handle:
            payload = await self._authed_request_json(
                "POST",
                "/media/upload",
                extra_params={"type": media_type},
                files={"media": (file_path.name, handle, "application/octet-stream")},
            )
        return str(payload["media_id"])

    async def send_file(self, *, target_kind: str, target_id: str, media_id: str) -> dict[str, Any]:
        payload = {
            "agentid": self.agent_id,
            "msgtype": "file",
            "file": {"media_id": media_id},
            "safe": 0,
            "enable_duplicate_check": 0,
        }
        payload[self._target_field(target_kind)] = target_id
        return await self._authed_request_json("POST", "/message/send", json_body=payload)

    @staticmethod
    def _target_field(target_kind: str) -> str:
        if target_kind == "chat":
            return "chatid"
        return "touser"


class WecomRobotClient:
    """WeCom group robot sender."""

    def __init__(self, webhook: str, *, secret: str | None = None, timeout: float = 10.0) -> None:
        self.webhook = webhook
        self.secret = secret
        self.timeout = timeout

    def _signed_url(self, url: str) -> str:
        if not self.secret:
            return url
        timestamp = str(int(time.time()))
        sign_bytes = hmac.new(self.secret.encode("utf-8"), f"{timestamp}\n{self.secret}".encode("utf-8"), hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(sign_bytes).decode("utf-8"))
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}timestamp={timestamp}&sign={sign}"

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._signed_url(url), json=payload)
            response.raise_for_status()
            data = response.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"WeCom robot API error {data.get('errcode')}: {data.get('errmsg')}")
        return data

    async def send_text(self, content: str) -> dict[str, Any]:
        return await self._post_json(_WECOM_ROBOT_SEND_URL, {"msgtype": "text", "text": {"content": content}})

    async def send_markdown(self, content: str) -> dict[str, Any]:
        return await self._post_json(_WECOM_ROBOT_SEND_URL, {"msgtype": "markdown", "markdown": {"content": content}})

    async def upload_file(self, file_path: Path) -> str:
        parsed = urllib.parse.urlparse(self.webhook)
        key = urllib.parse.parse_qs(parsed.query).get("key", [""])[0]
        if not key:
            raise ValueError("WeCom robot webhook is missing key query parameter")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(file_path, "rb") as handle:
                response = await client.post(
                    self._signed_url(f"{_WECOM_ROBOT_UPLOAD_URL}?key={key}&type=file"),
                    files={"media": (file_path.name, handle, "application/octet-stream")},
                )
            response.raise_for_status()
            data = response.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"WeCom robot upload error {data.get('errcode')}: {data.get('errmsg')}")
        return str(data["media_id"])

    async def send_file(self, file_path: Path) -> dict[str, Any]:
        media_id = await self.upload_file(file_path)
        return await self._post_json(_WECOM_ROBOT_SEND_URL, {"msgtype": "file", "file": {"media_id": media_id}})


class WecomChannel(Channel):
    """Enterprise WeChat channel supporting long connection and callback modes."""

    def __init__(self, bus: MessageBus, config: dict[str, Any]) -> None:
        super().__init__(name="wecom", bus=bus, config=config)
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._mode = str(config.get("mode", "long_connection")).strip().lower() or "long_connection"

        self._ws_client = None
        self._client = None
        self._crypto = None
        self._reply_frames: dict[str, Mapping[str, Any]] = {}
        self._stream_ids: dict[str, str] = {}

        self._bot_id = str(config.get("bot_id", "")).strip()
        self._bot_secret = str(config.get("bot_secret", config.get("secret", ""))).strip()

        self._corp_id = str(config.get("corp_id", "")).strip()
        self._agent_id = str(config.get("agent_id", "")).strip()
        self._agent_secret = str(config.get("agent_secret", config.get("secret", ""))).strip()
        self._token = str(config.get("token", "")).strip()
        self._encoding_aes_key = str(config.get("encoding_aes_key", "")).strip()

        timeout = float(config.get("timeout", 10.0))
        if self._mode == "callback" and self._corp_id and self._agent_id and self._agent_secret:
            self._client = WecomClient(self._corp_id, self._agent_id, self._agent_secret, timeout=timeout)
        if self._mode == "callback" and self._token and self._encoding_aes_key and self._corp_id:
            self._crypto = WecomCrypto(self._token, self._encoding_aes_key, self._corp_id)

        robot_config = config.get("robot", {}) if isinstance(config.get("robot"), dict) else {}
        self._robot_sync_push = bool(robot_config.get("enabled", False) and robot_config.get("sync_push_on_final", False))
        self._robot_client = None
        webhook = str(robot_config.get("webhook", "")).strip()
        if webhook:
            self._robot_client = WecomRobotClient(
                webhook,
                secret=str(robot_config.get("secret", "")).strip() or None,
                timeout=float(robot_config.get("timeout", 10.0)),
            )
        self._download_timeout = float(config.get("download_timeout", timeout))

    async def start(self) -> None:
        if self._running:
            return

        self._main_loop = asyncio.get_event_loop()
        self.bus.subscribe_outbound(self._on_outbound)

        if self._mode == "long_connection":
            started = await self._start_long_connection()
            if not started:
                self.bus.unsubscribe_outbound(self._on_outbound)
                return
        else:
            logger.info("WeCom callback mode enabled")

        self._running = True
        logger.info("WeCom channel started (mode=%s)", self._mode)

    async def stop(self) -> None:
        self._running = False
        self.bus.unsubscribe_outbound(self._on_outbound)

        if self._ws_client is not None:
            disconnect = getattr(self._ws_client, "disconnect", None)
            if disconnect is not None:
                await disconnect()
            self._ws_client = None

        logger.info("WeCom channel stopped")

    async def _start_long_connection(self) -> bool:
        if not self._bot_id or not self._bot_secret:
            logger.error("WeCom long_connection mode requires bot_id and bot_secret")
            return False

        try:
            from wecom_aibot_sdk import WSClient, generate_req_id
        except ImportError:
            logger.error("wecom-aibot-sdk is not installed. Install it with: uv add wecom-aibot-sdk")
            return False

        self._generate_req_id = generate_req_id
        ws_client = WSClient(bot_id=self._bot_id, secret=self._bot_secret)
        ws_client.on("authenticated", self._on_authenticated)
        ws_client.on("message.text", self._on_ws_text)
        ws_client.on("message.image", self._on_ws_image)
        ws_client.on("message.mixed", self._on_ws_mixed)
        ws_client.on("event.enter_chat", self._on_enter_chat)
        self._ws_client = ws_client
        await ws_client.connect()
        return True

    async def send(self, msg: OutboundMessage, *, _max_retries: int = 3) -> None:
        text = (msg.text or "").strip()
        if text:
            last_exc: Exception | None = None
            for attempt in range(_max_retries):
                try:
                    if self._mode == "long_connection":
                        await self._send_ws_text(msg.chat_id, text, thread_ts=msg.thread_ts, is_final=msg.is_final)
                    else:
                        target_kind, target_id = self._decode_target(msg.chat_id)
                        await self._send_app_text(target_kind=target_kind, target_id=target_id, text=text)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < _max_retries - 1:
                        await asyncio.sleep(2**attempt)
            if last_exc is not None:
                raise last_exc

        if self._robot_client and self._robot_sync_push and msg.is_final and text:
            await self._send_robot_text(text)

    async def send_file(self, msg: OutboundMessage, attachment: ResolvedAttachment) -> bool:
        uploaded = False

        if self._mode == "long_connection" and self._ws_client is not None:
            try:
                file_data = attachment.actual_path.read_bytes()
                upload_result = await self._ws_client.upload_media(file_data, type="file", filename=attachment.filename)
                media_id = str(upload_result["media_id"])
                await self._ws_client.send_media_message(self._strip_target_prefix(msg.chat_id), "file", media_id)
                uploaded = True
            except Exception:
                logger.exception("[WeCom] failed to upload long-connection file: %s", attachment.filename)
        elif self._client is not None:
            try:
                target_kind, target_id = self._decode_target(msg.chat_id)
                media_id = await self._client.upload_media(attachment.actual_path)
                await self._client.send_file(target_kind=target_kind, target_id=target_id, media_id=media_id)
                uploaded = True
            except Exception:
                logger.exception("[WeCom] failed to upload callback/app file: %s", attachment.filename)

        if self._robot_client and self._robot_sync_push and msg.is_final:
            try:
                await self._robot_client.send_file(attachment.actual_path)
                uploaded = True
            except Exception:
                logger.exception("[WeCom] failed to upload robot file: %s", attachment.filename)

        return uploaded

    @property
    def callback_enabled(self) -> bool:
        return self._mode == "callback" and self._crypto is not None

    async def verify_callback_url(self, *, signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        if self._mode != "callback" or not self._crypto:
            raise RuntimeError("WeCom callback mode is not enabled")
        return self._crypto.decrypt_message(signature, timestamp, nonce, echostr)

    async def handle_callback(self, *, signature: str, timestamp: str, nonce: str, body: bytes) -> InboundMessage | None:
        if self._mode != "callback" or not self._crypto:
            raise RuntimeError("WeCom callback mode is not enabled")
        root = ET.fromstring(body.decode("utf-8"))
        encrypt_node = root.find("Encrypt")
        if encrypt_node is None or not encrypt_node.text:
            raise ValueError("WeCom callback payload missing Encrypt")
        plain_xml = self._crypto.decrypt_message(signature, timestamp, nonce, encrypt_node.text)
        inbound = self._parse_plain_message(plain_xml)
        if inbound:
            await self.bus.publish_inbound(inbound)
        return inbound

    async def _send_ws_text(self, chat_id: str, text: str, *, thread_ts: str | None = None, is_final: bool = True) -> None:
        if self._ws_client is None:
            raise RuntimeError("WeCom long connection is not configured")
        if thread_ts and thread_ts in self._reply_frames:
            stream_id = self._stream_ids.get(thread_ts)
            if not stream_id:
                stream_id = self._generate_req_id("stream") if hasattr(self, "_generate_req_id") else f"stream-{int(time.time() * 1000)}"
                self._stream_ids[thread_ts] = stream_id
            await self._ws_client.reply_stream(self._reply_frames[thread_ts], stream_id, text, finish=is_final)
            if is_final:
                self._stream_ids.pop(thread_ts, None)
                self._reply_frames.pop(thread_ts, None)
            return
        if not is_final:
            return
        await self._ws_client.send_message(self._strip_target_prefix(chat_id), _markdown_body(text))

    async def _send_app_text(self, *, target_kind: str, target_id: str, text: str) -> None:
        if not self._client:
            raise RuntimeError("WeCom application client is not configured")
        if _prefer_markdown(text):
            try:
                await self._client.send_markdown(target_kind=target_kind, target_id=target_id, content=text)
                return
            except Exception:
                logger.warning("[WeCom] markdown send failed, falling back to text", exc_info=True)
        await self._client.send_text(target_kind=target_kind, target_id=target_id, content=text)

    async def _send_robot_text(self, text: str) -> None:
        if not self._robot_client:
            return
        if _prefer_markdown(text):
            try:
                await self._robot_client.send_markdown(text)
                return
            except Exception:
                logger.warning("[WeCom] robot markdown send failed, falling back to text", exc_info=True)
        await self._robot_client.send_text(text)

    async def _on_authenticated(self) -> None:
        logger.info("[WeCom] long connection authenticated")

    async def _on_enter_chat(self, frame: Mapping[str, Any]) -> None:
        welcome_text = str(self.config.get("welcome_text", "")).strip()
        if not welcome_text or self._ws_client is None:
            return
        try:
            await self._ws_client.reply_welcome(frame, _text_body(welcome_text))
        except Exception:
            logger.warning("[WeCom] failed to send welcome message", exc_info=True)

    async def _on_ws_text(self, frame: Mapping[str, Any]) -> None:
        inbound = await self._parse_ws_frame(frame, forced_msgtype="text")
        if inbound is not None:
            if inbound.thread_ts:
                self._reply_frames[inbound.thread_ts] = frame
            await self.bus.publish_inbound(inbound)
        else:
            logger.info("[WeCom] skipped inbound frame: forced=text frame_keys=%s", sorted(frame.keys()))

    async def _on_ws_image(self, frame: Mapping[str, Any]) -> None:
        inbound = await self._parse_ws_frame(frame, forced_msgtype="image")
        if inbound is not None:
            if inbound.thread_ts:
                self._reply_frames[inbound.thread_ts] = frame
            await self.bus.publish_inbound(inbound)
        else:
            logger.info("[WeCom] skipped inbound frame: forced=image frame_keys=%s", sorted(frame.keys()))

    async def _on_ws_mixed(self, frame: Mapping[str, Any]) -> None:
        inbound = await self._parse_ws_frame(frame, forced_msgtype="mixed")
        if inbound is not None:
            if inbound.thread_ts:
                self._reply_frames[inbound.thread_ts] = frame
            await self.bus.publish_inbound(inbound)
        else:
            logger.info("[WeCom] skipped inbound frame: forced=mixed frame_keys=%s", sorted(frame.keys()))

    async def _parse_ws_frame(
        self,
        frame: Mapping[str, Any],
        *,
        forced_msgtype: str | None = None,
    ) -> InboundMessage | None:
        raw_body = frame.get("body")
        body: Mapping[str, Any]
        if isinstance(raw_body, Mapping):
            body = raw_body
        else:
            body = frame

        content, files = await self._extract_ws_message_parts(frame, body, forced_msgtype=forced_msgtype)
        if not content and not files:
            return None

        raw_chat_id = _first_non_empty(body, "chatid", "chat_id", "conversation_id", "chatId")
        raw_user_id = _first_non_empty(
            body,
            "userid",
            "user_id",
            "from_userid",
            "fromUserId",
            nested_keys=[("from", "userid"), ("sender", "userid"), ("from", "user_id"), ("sender", "user_id")],
        )
        thread_ref = _first_non_empty(frame, "req_id", "msgid", "msg_id", "message_id") or _first_non_empty(
            body, "msgid", "msg_id", "message_id", "id"
        )

        if raw_chat_id:
            chat_id = f"chat:{raw_chat_id}"
            topic_id = raw_chat_id
        else:
            user_id = raw_user_id or "unknown"
            chat_id = f"user:{user_id}"
            topic_id = None

        inbound = self._make_inbound(
            chat_id=chat_id,
            user_id=raw_user_id or "unknown",
            text=content,
            msg_type=InboundMessageType.COMMAND if content.startswith("/") else InboundMessageType.CHAT,
            thread_ts=thread_ref or None,
            files=files,
            metadata={
                "platform": "wecom",
                "transport": "long_connection",
                "frame": dict(frame),
            },
        )
        inbound.topic_id = topic_id
        return inbound

    async def _extract_ws_message_parts(
        self,
        frame: Mapping[str, Any],
        body: Mapping[str, Any],
        *,
        forced_msgtype: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        text_parts: list[str] = []
        file_parts: list[dict[str, Any]] = []

        text_block = body.get("text")
        if isinstance(text_block, Mapping):
            text_value = text_block.get("content")
            if isinstance(text_value, str) and text_value.strip():
                text_parts.append(text_value.strip())
        elif isinstance(body.get("content"), str) and str(body.get("content")).strip():
            text_parts.append(str(body.get("content")).strip())

        direct_image = body.get("image")
        if isinstance(direct_image, Mapping):
            file_parts.append(await self._download_ws_image(frame, direct_image, 0))

        image_list = body.get("images")
        if isinstance(image_list, list):
            for index, image_payload in enumerate(image_list, start=len(file_parts)):
                if isinstance(image_payload, Mapping):
                    file_parts.append(await self._download_ws_image(frame, image_payload, index))

        raw_msg_type = str(forced_msgtype or frame.get("msgtype") or body.get("msgtype") or "").strip().lower()
        mixed_source: Any = (
            body.get("mixed")
            or body.get("items")
            or body.get("msg_items")
            or body.get("mixed_items")
        )
        if mixed_source is None and raw_msg_type == "mixed":
            mixed_source = body.get("content")
        if mixed_source is None and raw_msg_type == "mixed":
            mixed_source = body
        mixed_text, mixed_files = await self._extract_ws_mixed_parts(frame, mixed_source)
        if raw_msg_type == "mixed" and not mixed_text and not mixed_files:
            mixed_text, mixed_files = await self._extract_ws_mixed_parts_fallback(frame, body)
        text_parts.extend(mixed_text)
        file_parts.extend(mixed_files)

        return "\n".join(part for part in text_parts if part).strip(), file_parts

    async def _extract_ws_mixed_parts(
        self,
        frame: Mapping[str, Any],
        mixed_payload: Any,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if mixed_payload is None:
            return [], []

        parsed_payload = mixed_payload
        if isinstance(parsed_payload, str):
            try:
                parsed_payload = json.loads(parsed_payload)
            except json.JSONDecodeError:
                return [], []

        items: Any = None
        if isinstance(parsed_payload, list):
            items = parsed_payload
        elif isinstance(parsed_payload, Mapping):
            items = (
                parsed_payload.get("items")
                or parsed_payload.get("content")
                or parsed_payload.get("list")
                or parsed_payload.get("msg_items")
            )
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    items = None
            if items is None and any(key in parsed_payload for key in ("image", "images", "text", "content", "url", "download_url", "image_url", "cdn_url")):
                items = [parsed_payload]

        if not isinstance(items, list):
            return [], []

        text_parts: list[str] = []
        file_parts: list[dict[str, Any]] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                continue

            item_type = str(item.get("type") or item.get("msgtype") or "").strip().lower()
            if not item_type:
                if any(key in item for key in ("image", "images", "url", "download_url", "image_url", "cdn_url")):
                    item_type = "image"
                elif any(key in item for key in ("text", "content")):
                    item_type = "text"
            if item_type == "text":
                nested_text = item.get("text")
                if isinstance(nested_text, Mapping):
                    text_value = nested_text.get("content")
                    if isinstance(text_value, str) and text_value.strip():
                        text_parts.append(text_value.strip())
                elif isinstance(item.get("content"), str) and str(item.get("content")).strip():
                    text_parts.append(str(item.get("content")).strip())
                continue

            if item_type == "image":
                image_payload = item.get("image")
                if isinstance(item.get("images"), list):
                    for offset, nested_image in enumerate(item["images"], start=len(file_parts)):
                        if isinstance(nested_image, Mapping):
                            file_parts.append(await self._download_ws_image(frame, nested_image, index + offset))
                    continue
                if not isinstance(image_payload, Mapping) and any(key in item for key in ("url", "download_url", "image_url", "cdn_url")):
                    image_payload = item
                if isinstance(image_payload, Mapping):
                    file_parts.append(await self._download_ws_image(frame, image_payload, index))

        return text_parts, file_parts

    async def _extract_ws_mixed_parts_fallback(
        self,
        frame: Mapping[str, Any],
        payload: Any,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        text_parts: list[str] = []
        file_parts: list[dict[str, Any]] = []
        seen_texts: set[str] = set()
        seen_images: set[str] = set()

        async def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    await walk(item)
                return

            if not isinstance(node, Mapping):
                return

            nested_text = node.get("text")
            if isinstance(nested_text, Mapping):
                text_value = nested_text.get("content")
                if isinstance(text_value, str):
                    cleaned = text_value.strip()
                    if cleaned and cleaned not in seen_texts:
                        seen_texts.add(cleaned)
                        text_parts.append(cleaned)

            direct_content = node.get("content")
            if isinstance(direct_content, str):
                cleaned = direct_content.strip()
                if (
                    cleaned
                    and not cleaned.startswith("{")
                    and not cleaned.startswith("[")
                    and not cleaned.startswith("http://")
                    and not cleaned.startswith("https://")
                    and cleaned not in seen_texts
                ):
                    seen_texts.add(cleaned)
                    text_parts.append(cleaned)

            image_payload = node.get("image")
            if isinstance(image_payload, Mapping):
                image_key = str(
                    _first_non_empty(
                        image_payload,
                        "url",
                        "download_url",
                        "image_url",
                        "cdn_url",
                    )
                    or _first_non_empty(node, "msgid", "msg_id", "id")
                    or len(file_parts)
                )
                if image_key not in seen_images:
                    seen_images.add(image_key)
                    file_parts.append(await self._download_ws_image(frame, image_payload, len(file_parts)))

            if isinstance(node.get("images"), list):
                for nested_image in node["images"]:
                    if isinstance(nested_image, Mapping):
                        image_key = str(
                            _first_non_empty(
                                nested_image,
                                "url",
                                "download_url",
                                "image_url",
                                "cdn_url",
                            )
                            or len(file_parts)
                        )
                        if image_key not in seen_images:
                            seen_images.add(image_key)
                            file_parts.append(await self._download_ws_image(frame, nested_image, len(file_parts)))

            for key in ("msg_item", "msgItem", "items", "msg_items", "mixed", "mixed_items", "content", "list"):
                if key in node:
                    await walk(node.get(key))

            for value in node.values():
                if isinstance(value, (Mapping, list)):
                    await walk(value)

        await walk(payload)
        return text_parts, file_parts

    async def _download_ws_image(
        self,
        frame: Mapping[str, Any],
        image_payload: Mapping[str, Any],
        index: int,
    ) -> dict[str, Any]:
        image_url = _first_non_empty(
            image_payload,
            "url",
            "download_url",
            "image_url",
            "cdn_url",
        )
        aes_key = _first_non_empty(image_payload, "aeskey", "aes_key", "key")
        if not image_url:
            return {"error": f"第 {index + 1} 张图片缺少可下载地址，已跳过。", "is_image": True}

        msg_ref = _first_non_empty(frame, "req_id", "msgid", "msg_id", "message_id") or f"frame-{index + 1}"
        suffix = Path(urllib.parse.urlparse(image_url).path).suffix or ".jpg"
        filename = str(image_payload.get("filename") or f"wecom-{msg_ref}-{index + 1}{suffix}")
        mime_type = image_payload.get("mime_type")
        if not isinstance(mime_type, str) or not mime_type:
            mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"

        try:
            buffer = await self._download_long_connection_media(image_url, aes_key)
        except Exception as exc:
            logger.warning("[WeCom] failed to download image payload: %s", exc, exc_info=True)
            return {"error": f"第 {index + 1} 张图片下载失败，已跳过。", "is_image": True}

        return {
            "filename": filename,
            "mime_type": mime_type,
            "size": len(buffer),
            "buffer": buffer,
            "is_image": True,
        }

    async def _download_long_connection_media(self, url: str, aes_key: str | None = None) -> bytes:
        if self._ws_client is not None:
            download_file = getattr(self._ws_client, "download_file", None)
            if download_file is not None:
                try:
                    result = await download_file(url, aes_key) if aes_key else await download_file(url)
                except TypeError:
                    result = await download_file(url, aes_key)
                if isinstance(result, bytes):
                    return result
                if isinstance(result, bytearray):
                    return bytes(result)
                if isinstance(result, Mapping):
                    for key in ("data", "content", "file_bytes", "bytes"):
                        value = result.get(key)
                        if isinstance(value, bytes):
                            return value
                        if isinstance(value, bytearray):
                            return bytes(value)
                    buffer = result.get("buffer")
                    if isinstance(buffer, bytes):
                        return buffer
                    if isinstance(buffer, bytearray):
                        return bytes(buffer)

        async with httpx.AsyncClient(timeout=self._download_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _parse_plain_message(self, plain_xml: str) -> InboundMessage | None:
        root = ET.fromstring(plain_xml)
        msg_type = (root.findtext("MsgType") or "").strip().lower()
        if msg_type == "event":
            event = (root.findtext("Event") or "").strip().lower()
            logger.info("[WeCom] ignoring event callback: %s", event)
            return None

        if msg_type != "text":
            logger.info("[WeCom] unsupported inbound message type: %s", msg_type)
            return None

        content = (root.findtext("Content") or "").strip()
        if not content:
            return None

        from_user = (root.findtext("FromUserName") or "").strip()
        raw_chat_id = (root.findtext("ChatId") or "").strip()
        raw_msg_id = (root.findtext("MsgId") or root.findtext("MsgID") or "").strip()
        raw_thread = raw_msg_id or (root.findtext("CreateTime") or "").strip() or None

        if raw_chat_id:
            chat_id = f"chat:{raw_chat_id}"
            topic_id = raw_chat_id
        else:
            chat_id = f"user:{from_user}"
            topic_id = None

        inbound = self._make_inbound(
            chat_id=chat_id,
            user_id=from_user,
            text=content,
            msg_type=InboundMessageType.COMMAND if content.startswith("/") else InboundMessageType.CHAT,
            thread_ts=raw_thread,
            metadata={
                "platform": "wecom",
                "transport": "callback",
                "raw_chat_id": raw_chat_id,
                "msg_id": raw_msg_id,
                "msg_type": msg_type,
            },
        )
        inbound.topic_id = topic_id
        return inbound

    @staticmethod
    def _decode_target(chat_id: str) -> tuple[str, str]:
        if chat_id.startswith("chat:"):
            return "chat", chat_id.removeprefix("chat:")
        if chat_id.startswith("user:"):
            return "user", chat_id.removeprefix("user:")
        return "user", chat_id

    @staticmethod
    def _strip_target_prefix(chat_id: str) -> str:
        if ":" in chat_id:
            return chat_id.split(":", 1)[1]
        return chat_id


def _prefer_markdown(text: str) -> bool:
    markers = ("```", "# ", "> ", "- ", "* ", "|", "[", "]", "\n")
    return any(marker in text for marker in markers)


def _text_body(content: str) -> dict[str, Any]:
    return {"msgtype": "text", "text": {"content": content}}


def _markdown_body(content: str) -> dict[str, Any]:
    return {"msgtype": "markdown", "markdown": {"content": content}}


def _first_non_empty(
    mapping: Mapping[str, Any],
    *keys: str,
    nested_keys: list[tuple[str, str]] | None = None,
) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for outer_key, inner_key in nested_keys or []:
        outer_value = mapping.get(outer_key)
        if isinstance(outer_value, Mapping):
            inner_value = outer_value.get(inner_key)
            if isinstance(inner_value, str) and inner_value.strip():
                return inner_value.strip()
    return ""
