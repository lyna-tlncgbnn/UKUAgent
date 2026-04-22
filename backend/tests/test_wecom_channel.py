from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.channels.message_bus import MessageBus, OutboundMessage, ResolvedAttachment
from app.channels.wecom import WecomChannel, WecomCrypto
from pathlib import Path


_CHANNELS_ROUTER_SPEC = importlib.util.spec_from_file_location(
    "channels_router_module",
    Path(__file__).resolve().parent.parent / "app" / "gateway" / "routers" / "channels.py",
)
channels_router = importlib.util.module_from_spec(_CHANNELS_ROUTER_SPEC)
assert _CHANNELS_ROUTER_SPEC.loader is not None
_CHANNELS_ROUTER_SPEC.loader.exec_module(channels_router)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestWecomCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        crypto = WecomCrypto(
            token="test-token",
            encoding_aes_key="abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
            receive_id="corp-test",
        )
        encrypted = crypto.encrypt("<xml><Content>hello</Content></xml>")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == "<xml><Content>hello</Content></xml>"

    def test_verify_signature_and_decrypt_message(self):
        crypto = WecomCrypto(
            token="token-1",
            encoding_aes_key="abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
            receive_id="corp-id",
        )
        encrypted = crypto.encrypt("<xml><MsgType>text</MsgType></xml>")
        signature = hashlib.sha1("".join(sorted(["token-1", "123", "nonce", encrypted])).encode("utf-8")).hexdigest()
        assert crypto.decrypt_message(signature, "123", "nonce", encrypted) == "<xml><MsgType>text</MsgType></xml>"


class TestWecomChannel:
    def test_parse_long_connection_frame(self):
        channel = WecomChannel(
            MessageBus(),
            {
                "mode": "long_connection",
                "bot_id": "bot-1",
                "bot_secret": "secret-1",
            },
        )
        inbound = _run(
            channel._parse_ws_frame(
                {
                    "req_id": "req-1",
                    "body": {
                        "chatid": "chat-123",
                        "userid": "user-1",
                        "text": {"content": "/status"},
                    },
                }
            )
        )
        assert inbound is not None
        assert inbound.chat_id == "chat:chat-123"
        assert inbound.user_id == "user-1"
        assert inbound.msg_type.value == "command"
        assert inbound.topic_id == "chat-123"

    def test_parse_long_connection_frame_reads_nested_sender(self):
        channel = WecomChannel(
            MessageBus(),
            {
                "mode": "long_connection",
                "bot_id": "bot-1",
                "bot_secret": "secret-1",
            },
        )
        inbound = _run(
            channel._parse_ws_frame(
                {
                    "msgid": "msg-1",
                    "body": {
                        "chattype": "single",
                        "from": {"userid": "10300090"},
                        "text": {"content": "hello"},
                    },
                }
            )
        )
        assert inbound is not None
        assert inbound.chat_id == "user:10300090"
        assert inbound.user_id == "10300090"

    def test_parse_long_connection_image_frame_downloads_image(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.download_file = AsyncMock(return_value=b"image-bytes")

            inbound = await channel._parse_ws_frame(
                {
                    "msgid": "msg-image-1",
                    "body": {
                        "from": {"userid": "10300090"},
                        "image": {"url": "https://example.com/img.png", "aeskey": "k1"},
                    },
                }
            )

            assert inbound is not None
            assert inbound.chat_id == "user:10300090"
            assert inbound.text == ""
            assert len(inbound.files) == 1
            assert inbound.files[0]["buffer"] == b"image-bytes"
            assert inbound.files[0]["is_image"] is True
            channel._ws_client.download_file.assert_awaited_once()

        _run(go())

    def test_parse_long_connection_mixed_frame_supports_text_and_multiple_images(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.download_file = AsyncMock(side_effect=[b"img-1", b"img-2"])

            inbound = await channel._parse_ws_frame(
                {
                    "req_id": "req-mixed-1",
                    "body": {
                        "chatid": "chat-123",
                        "userid": "user-1",
                        "mixed": {
                            "items": [
                                {"type": "text", "text": {"content": "帮我看看这两张图"}},
                                {"type": "image", "image": {"url": "https://example.com/1.png", "aeskey": "k1"}},
                                {"type": "image", "image": {"url": "https://example.com/2.png", "aeskey": "k2"}},
                            ]
                        },
                    },
                }
            )

            assert inbound is not None
            assert inbound.chat_id == "chat:chat-123"
            assert inbound.text == "帮我看看这两张图"
            assert len(inbound.files) == 2
            assert [f["buffer"] for f in inbound.files] == [b"img-1", b"img-2"]

        _run(go())

    def test_parse_long_connection_mixed_frame_with_forced_type(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.download_file = AsyncMock(return_value=b"img-1")

            inbound = await channel._parse_ws_frame(
                {
                    "req_id": "req-mixed-forced-1",
                    "body": {
                        "from": {"userid": "10300090"},
                        "text": {"content": "帮我看看这张图"},
                        "image": {"url": "https://example.com/1.png", "aeskey": "k1"},
                    },
                },
                forced_msgtype="mixed",
            )

            assert inbound is not None
            assert inbound.chat_id == "user:10300090"
            assert inbound.text == "帮我看看这张图"
            assert len(inbound.files) == 1
            assert inbound.files[0]["buffer"] == b"img-1"

        _run(go())

    def test_parse_long_connection_image_failure_preserves_note(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.download_file = AsyncMock(side_effect=RuntimeError("boom"))

            inbound = await channel._parse_ws_frame(
                {
                    "msgid": "msg-image-2",
                    "body": {
                        "from": {"userid": "10300090"},
                        "image": {"url": "https://example.com/img.png", "aeskey": "k1"},
                    },
                }
            )

            assert inbound is not None
            assert len(inbound.files) == 1
            assert "下载失败" in inbound.files[0]["error"]

        _run(go())

    def test_parse_user_text_message(self):
        channel = WecomChannel(
            MessageBus(),
            {
                "mode": "callback",
                "corp_id": "corp",
                "agent_id": "1000001",
                "agent_secret": "secret",
                "token": "token",
                "encoding_aes_key": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
            },
        )
        inbound = channel._parse_plain_message(
            """
            <xml>
              <ToUserName><![CDATA[corp]]></ToUserName>
              <FromUserName><![CDATA[zhangsan]]></FromUserName>
              <CreateTime>1711111111</CreateTime>
              <MsgType><![CDATA[text]]></MsgType>
              <Content><![CDATA[/status]]></Content>
              <MsgId>msg-1</MsgId>
            </xml>
            """
        )
        assert inbound is not None
        assert inbound.chat_id == "user:zhangsan"
        assert inbound.user_id == "zhangsan"
        assert inbound.msg_type.value == "command"
        assert inbound.topic_id is None

    def test_parse_group_text_message(self):
        channel = WecomChannel(
            MessageBus(),
            {
                "mode": "callback",
                "corp_id": "corp",
                "agent_id": "1000001",
                "agent_secret": "secret",
                "token": "token",
                "encoding_aes_key": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
            },
        )
        inbound = channel._parse_plain_message(
            """
            <xml>
              <ToUserName><![CDATA[corp]]></ToUserName>
              <FromUserName><![CDATA[lisi]]></FromUserName>
              <CreateTime>1711111111</CreateTime>
              <MsgType><![CDATA[text]]></MsgType>
              <Content><![CDATA[hello group]]></Content>
              <MsgId>msg-2</MsgId>
              <ChatId><![CDATA[chat123]]></ChatId>
            </xml>
            """
        )
        assert inbound is not None
        assert inbound.chat_id == "chat:chat123"
        assert inbound.topic_id == "chat123"

    def test_send_prefers_markdown_and_syncs_robot(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "callback",
                    "corp_id": "corp",
                    "agent_id": "1000001",
                    "agent_secret": "secret",
                    "robot": {
                        "enabled": True,
                        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
                        "sync_push_on_final": True,
                    },
                },
            )
            channel._client = MagicMock()
            channel._client.send_markdown = AsyncMock(return_value={})
            channel._client.send_text = AsyncMock(return_value={})
            channel._robot_client = MagicMock()
            channel._robot_client.send_markdown = AsyncMock(return_value={})
            channel._robot_client.send_text = AsyncMock(return_value={})

            await channel.send(
                OutboundMessage(
                    channel_name="wecom",
                    chat_id="user:zhangsan",
                    thread_id="t1",
                    text="# title\n- item",
                    is_final=True,
                )
            )

            channel._client.send_markdown.assert_awaited_once()
            channel._robot_client.send_markdown.assert_awaited_once()

        _run(go())

    def test_long_connection_send_prefers_markdown_and_syncs_robot(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                    "robot": {
                        "enabled": True,
                        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
                        "sync_push_on_final": True,
                    },
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.send_message = AsyncMock(return_value={})
            channel._robot_client = MagicMock()
            channel._robot_client.send_markdown = AsyncMock(return_value={})

            await channel.send(
                OutboundMessage(
                    channel_name="wecom",
                    chat_id="chat:group-1",
                    thread_id="t1",
                    text="# hello\n- item",
                    is_final=True,
                )
            )

            channel._ws_client.send_message.assert_awaited_once()
            args = channel._ws_client.send_message.await_args.args
            assert args[0] == "group-1"
            assert args[1]["msgtype"] == "markdown"
            channel._robot_client.send_markdown.assert_awaited_once()

        _run(go())

    def test_long_connection_send_replies_to_original_frame(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            frame = {
                "req_id": "req-123",
                "body": {
                    "from": {"userid": "10300090"},
                    "text": {"content": "hi"},
                },
            }
            channel._ws_client = MagicMock()
            channel._ws_client.reply_stream = AsyncMock(return_value={})
            channel._ws_client.send_message = AsyncMock(return_value={})
            channel._generate_req_id = lambda prefix: "stream-1"

            await channel._on_ws_text(frame)
            await channel.send(
                OutboundMessage(
                    channel_name="wecom",
                    chat_id="user:10300090",
                    thread_id="t1",
                    thread_ts="req-123",
                    text="hello back",
                    is_final=True,
                )
            )

            channel._ws_client.reply_stream.assert_awaited_once_with(frame, "stream-1", "hello back", finish=True)
            channel._ws_client.send_message.assert_not_called()

        _run(go())

    def test_long_connection_stream_reuses_stream_id_until_final(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            frame = {
                "req_id": "req-456",
                "body": {
                    "from": {"userid": "10300090"},
                    "text": {"content": "hi"},
                },
            }
            channel._ws_client = MagicMock()
            channel._ws_client.reply_stream = AsyncMock(return_value={})
            channel._ws_client.send_message = AsyncMock(return_value={})
            channel._generate_req_id = lambda prefix: "stream-2"

            await channel._on_ws_text(frame)
            await channel.send(
                OutboundMessage(
                    channel_name="wecom",
                    chat_id="user:10300090",
                    thread_id="t1",
                    thread_ts="req-456",
                    text="thinking...",
                    is_final=False,
                )
            )
            await channel.send(
                OutboundMessage(
                    channel_name="wecom",
                    chat_id="user:10300090",
                    thread_id="t1",
                    thread_ts="req-456",
                    text="done",
                    is_final=True,
                )
            )

            assert channel._ws_client.reply_stream.await_count == 2
            first_call = channel._ws_client.reply_stream.await_args_list[0]
            second_call = channel._ws_client.reply_stream.await_args_list[1]
            assert first_call.args == (frame, "stream-2", "thinking...")
            assert first_call.kwargs == {"finish": False}
            assert second_call.args == (frame, "stream-2", "done")
            assert second_call.kwargs == {"finish": True}
            assert "req-456" not in channel._stream_ids

        _run(go())

    def test_send_file_uploads_to_app_and_robot(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "callback",
                    "corp_id": "corp",
                    "agent_id": "1000001",
                    "agent_secret": "secret",
                    "robot": {
                        "enabled": True,
                        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
                        "sync_push_on_final": True,
                    },
                },
            )
            channel._client = MagicMock()
            channel._client.upload_media = AsyncMock(return_value="media-1")
            channel._client.send_file = AsyncMock(return_value={})
            channel._robot_client = MagicMock()
            channel._robot_client.send_file = AsyncMock(return_value={})

            temp_handle = tempfile.NamedTemporaryFile(dir=Path.cwd(), suffix=".pdf", delete=False)
            temp_handle.close()
            test_file = Path(temp_handle.name)
            try:
                test_file.write_bytes(b"%PDF")
                attachment = ResolvedAttachment(
                    virtual_path="/mnt/user-data/outputs/report.pdf",
                    actual_path=test_file,
                    filename="report.pdf",
                    mime_type="application/pdf",
                    size=4,
                    is_image=False,
                )

                result = await channel.send_file(
                    OutboundMessage(
                        channel_name="wecom",
                        chat_id="chat:group-1",
                        thread_id="thread-1",
                        text="done",
                        is_final=True,
                    ),
                    attachment,
                )
            finally:
                try:
                    test_file.unlink(missing_ok=True)
                except PermissionError:
                    pass

            assert result is True
            channel._client.upload_media.assert_awaited_once()
            channel._client.send_file.assert_awaited_once()
            channel._robot_client.send_file.assert_awaited_once()

        _run(go())

    def test_send_file_uploads_via_long_connection(self):
        async def go():
            channel = WecomChannel(
                MessageBus(),
                {
                    "mode": "long_connection",
                    "bot_id": "bot-1",
                    "bot_secret": "secret-1",
                },
            )
            channel._ws_client = MagicMock()
            channel._ws_client.upload_media = AsyncMock(return_value={"media_id": "media-1"})
            channel._ws_client.send_media_message = AsyncMock(return_value={})

            temp_handle = tempfile.NamedTemporaryFile(dir=Path.cwd(), suffix=".pdf", delete=False)
            temp_handle.close()
            test_file = Path(temp_handle.name)
            try:
                test_file.write_bytes(b"%PDF")
                attachment = ResolvedAttachment(
                    virtual_path="/mnt/user-data/outputs/report.pdf",
                    actual_path=test_file,
                    filename="report.pdf",
                    mime_type="application/pdf",
                    size=4,
                    is_image=False,
                )

                result = await channel.send_file(
                    OutboundMessage(
                        channel_name="wecom",
                        chat_id="chat:group-2",
                        thread_id="thread-2",
                        text="done",
                        is_final=True,
                    ),
                    attachment,
                )
            finally:
                try:
                    test_file.unlink(missing_ok=True)
                except PermissionError:
                    pass

            assert result is True
            channel._ws_client.upload_media.assert_awaited_once()
            channel._ws_client.send_media_message.assert_awaited_once_with("group-2", "file", "media-1")

        _run(go())

    def test_handle_callback_publishes_inbound(self):
        async def go():
            bus = MessageBus()
            channel = WecomChannel(
                bus,
                {
                    "mode": "callback",
                    "corp_id": "corp-id",
                    "agent_id": "1000001",
                    "agent_secret": "secret",
                    "token": "token",
                    "encoding_aes_key": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
                },
            )
            plain_xml = (
                "<xml>"
                "<ToUserName><![CDATA[corp-id]]></ToUserName>"
                "<FromUserName><![CDATA[user-a]]></FromUserName>"
                "<CreateTime>1711111111</CreateTime>"
                "<MsgType><![CDATA[text]]></MsgType>"
                "<Content><![CDATA[hello]]></Content>"
                "<MsgId>msg-9</MsgId>"
                "</xml>"
            )
            encrypted = channel._crypto.encrypt(plain_xml)
            signature = hashlib.sha1("".join(sorted(["token", "123", "nonce", encrypted])).encode("utf-8")).hexdigest()
            callback_body = f"<xml><ToUserName><![CDATA[corp-id]]></ToUserName><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>".encode(
                "utf-8"
            )

            inbound = await channel.handle_callback(
                signature=signature,
                timestamp="123",
                nonce="nonce",
                body=callback_body,
            )
            queued = await bus.get_inbound()

            assert inbound is not None
            assert queued.chat_id == "user:user-a"
            assert queued.text == "hello"

        _run(go())


class TestWecomCallbackRouter:
    def test_verify_callback_route(self, monkeypatch):
        app = FastAPI()
        app.include_router(channels_router.router)
        channel = SimpleNamespace(
            verify_callback_url=AsyncMock(return_value="plain-echostr"),
            handle_callback=AsyncMock(),
        )
        service = SimpleNamespace(get_channel=lambda name: channel)
        monkeypatch.setattr("app.channels.service.get_channel_service", lambda: service)

        client = TestClient(app)
        response = client.get(
            "/api/channels/wecom/callback",
            params={
                "msg_signature": "sig",
                "timestamp": "1",
                "nonce": "n",
                "echostr": "echo",
            },
        )
        assert response.status_code == 200
        assert response.text == "plain-echostr"

    def test_receive_callback_route(self, monkeypatch):
        app = FastAPI()
        app.include_router(channels_router.router)
        channel = SimpleNamespace(
            verify_callback_url=AsyncMock(),
            handle_callback=AsyncMock(return_value=None),
        )
        service = SimpleNamespace(get_channel=lambda name: channel)
        monkeypatch.setattr("app.channels.service.get_channel_service", lambda: service)

        client = TestClient(app)
        response = client.post(
            "/api/channels/wecom/callback",
            params={"msg_signature": "sig", "timestamp": "1", "nonce": "n"},
            content=b"<xml></xml>",
        )
        assert response.status_code == 200
        assert response.text == "success"
        channel.handle_callback.assert_awaited_once()


class TestWecomStatus:
    def test_channel_service_reports_wecom(self):
        from app.channels.service import ChannelService

        service = ChannelService(channels_config={"wecom": {"enabled": False}})
        status = service.get_status()
        assert "wecom" in status["channels"]
