"""
Example: Send messages, emails, and call requests via voice.

    META_AI_API_KEY=<key> python examples/outreach_app.py
"""

import os

from metaglasses import Glasses, MetaAIClient, GlassesConnectionError
from metaglasses.apps.outreach import OutreachApp


def on_send(item):
    icons = {"message": "💬", "email": "✉️", "call": "📞"}
    icon = icons.get(item.type, "📤")
    if item.type == "call":
        print(f"  {icon} Calling: {item.to}")
    else:
        print(f"  {icon} To: {item.to}\n     {item.body}")


def main():
    api_key = os.environ.get("META_AI_API_KEY", "demo")

    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    ai = MetaAIClient(api_key=api_key) if api_key != "demo" else None
    app = OutreachApp(glasses, ai, on_send=on_send, polish_with_ai=(ai is not None))
    app.start()

    # Programmatic outreach
    print("Programmatic outreach:")
    app.send_message("Alex", "running 5 minutes late, be there soon")
    app.send_email("boss@example.com", "project milestone hit ahead of schedule")
    app.request_call("Mom")

    # Voice command simulations
    print("\nVoice command simulations:")
    print("  'hey meta, text Sarah: on my way'")
    app._handler.dispatch("hey meta, text Sarah: on my way")

    print("  'hey meta, email John: the report is ready for review'")
    app._handler.dispatch("hey meta, email John: the report is ready for review")

    print("  'hey meta, call Alice'")
    app._handler.dispatch("hey meta, call Alice")

    print(f"\nOutbox has {len(app.outbox)} items.")
    app.stop()
    glasses.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
