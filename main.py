import os
import time
import requests
import urllib.parse
import zulip

from markdownify import markdownify as md

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

STREAMS = os.environ.get(
    "ZULIP_STREAMS",
    "general"
).split(",")

ZULIP_SITE = os.environ["ZULIP_SITE"].rstrip("/")

client = zulip.Client(
    email=os.environ["ZULIP_EMAIL"],
    api_key=os.environ["ZULIP_API_KEY"],
    site=ZULIP_SITE,
)

client.add_subscriptions(
    [{"name": s.strip()} for s in STREAMS]
)

response = client.register(
    event_types=["message"]
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
            if event["type"] != "message":
                continue

            msg = event["message"]

            if msg["type"] != "stream":
                continue

            stream = msg["display_recipient"]

            if stream not in STREAMS:
                continue

            sender = msg["sender_full_name"]
            topic = msg["subject"]

            content = md(
                msg["content"],
                heading_style="ATX",
                bullets="-",
            )

            # Discord embed descriptions max out at 4096 chars
            content = content[:4000]

            stream_id = msg["stream_id"]
            message_id = msg["id"]

            encoded_stream = urllib.parse.quote(stream)
            encoded_topic = urllib.parse.quote(topic)

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
                "url": message_url,
                "description": content,
                "color": 0x4e5d94,
                "author": {
                    "name": sender,
                },
                "fields": [
                    {
                        "name": "Stream",
                        "value": f"[{stream}]({stream_url})",
                        "inline": True,
                    },
                    {
                        "name": "Topic",
                        "value": f"[{topic}]({topic_url})",
                        "inline": True,
                    },
                    {
                        "name": "Message",
                        "value": f"[Jump to message]({message_url})",
                        "inline": False,
                    },
                ],
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

            last_event_id = max(
                last_event_id,
                event["id"]
            )

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
