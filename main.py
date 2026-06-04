import os
import time
import requests
import urllib.parse
import zulip

from markdownify import markdownify as md

DEFAULT_COLOR = 0x4e5d94
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
ZULIP_SITE = os.environ["ZULIP_SITE"].rstrip("/")

STREAMS = {}

for entry in os.environ.get("ZULIP_STREAMS", "general").split(","):
    parts = entry.strip().split(":", 1)
    name = parts[0].strip()
    color = int(parts[1].strip().lstrip("#"), 16) if len(parts) > 1 else DEFAULT_COLOR
    STREAMS[name] = color

client = zulip.Client(
    email=os.environ["ZULIP_EMAIL"],
    api_key=os.environ["ZULIP_API_KEY"],
    site=ZULIP_SITE,
)

client.add_subscriptions(
    [{"name": stream} for stream in STREAMS]
)

response = client.register(
    event_types=["message"],
    apply_markdown=True,
)

queue_id = response["queue_id"]
last_event_id = response["last_event_id"]

print("Listening for Zulip messages...")

while True:
    try:
        events = client.get_events(
            queue_id=queue_id,
            last_event_id=last_event_id,
        )

        for event in events["events"]:
            last_event_id = max(
                last_event_id,
                event["id"]
            )

            if event["type"] != "message":
                continue

            msg = event["message"]

            if msg["type"] != "stream":
                continue

            stream = msg["display_recipient"]

            if stream not in STREAMS:
                continue

            sender = msg["sender_full_name"]
            sender_id = msg["sender_id"]
            sender_url = f"{ZULIP_SITE}/#user/{sender_id}"
            avatar_url = msg.get("avatar_url")
            topic = msg["subject"]

            content = md(
                msg["content"],
                heading_style="ATX",
                code_language="rust",
                code_language_callback=(lambda el:
                    el.parent['data-code-language'].lower() if el.parent.has_attr('data-code-language') else None
                )
            )

            content = content.replace("\n>\n", "\n> \n")
            content = content.replace("#narrow/channel", f"{ZULIP_SITE}/#narrow/channel")

            # Discord embed descriptions max out at 4096 chars
            content = content[:4000]

            stream_id = msg["stream_id"]
            message_id = msg["id"]

            encoded_stream = urllib.parse.quote(stream).replace(".", ".2E")
            encoded_topic = urllib.parse.quote(topic).replace(".", ".2E")

            stream_url = (
                f"{ZULIP_SITE}/#narrow/"
                f"channel/{stream_id}-{encoded_stream}"
            )

            topic_url = (
                f"{stream_url}/topic/{encoded_topic}"
            )

            message_url = (
                f"{topic_url}/near/{message_id}"
            )

            embed = {
                "title": f"{stream} / {topic}",
                "url": message_url.replace("%", "."),
                "description": content,
                "color": STREAMS.get(stream, DEFAULT_COLOR),
                "author": {
                    "name": sender,
                    "icon_url": avatar_url,
                    "url": sender_url,
                },
                "fields": []
            }

            requests.post(
                DISCORD_WEBHOOK,
                json={
                    "embeds": [embed],
                    "allowed_mentions": {
                        "parse": []
                    },
                },
            )

            print(f"Forwarded: {stream}/{topic}")


    except Exception as e:
        print("Error:", e)
        time.sleep(5)
