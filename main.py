import os
import time
import requests
import zulip

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

STREAMS = os.environ.get(
    "ZULIP_STREAMS",
    "general"
).split(",")

client = zulip.Client(
    email=os.environ["ZULIP_EMAIL"],
    api_key=os.environ["ZULIP_API_KEY"],
    site=os.environ["ZULIP_SITE"],
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

            # Zulip content is HTML
            content = msg["content"]

            text = (
                f"**{sender}** "
                f"in **{stream} / {topic}**\n"
                f"{content}"
            )

            requests.post(
                DISCORD_WEBHOOK,
                json={"content": text}
            )

            print(f"Forwarded: {stream}/{topic}")

            last_event_id = max(
                last_event_id,
                event["id"]
            )

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
