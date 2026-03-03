"""
Example: Ask Meta AI a question using the glasses as the trigger.

A voice command ("hey meta, ask ai …") captures the transcript and sends
it to the Meta AI API, then the response is read aloud via the glasses
speaker (text-to-speech is wired up separately in a real integration).

Run with:
    META_AI_API_KEY=<your-key> python examples/ai_assistant.py
"""

import os

from metaglasses import Glasses, VoiceCommandHandler, MetaAIClient, GlassesConnectionError
from metaglasses.ai import MetaAIError


def main():
    api_key = os.environ.get("META_AI_API_KEY", "")
    if not api_key:
        print("[WARN] META_AI_API_KEY not set — using demo mode (no real API calls).")

    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    ai = MetaAIClient(
        api_key=api_key or "demo",
        system_prompt=(
            "You are a helpful assistant running on Ray-Ban Meta Smart Glasses. "
            "Keep answers short and conversational."
        ),
    ) if api_key else None

    handler = VoiceCommandHandler(glasses)

    @handler.command("ask ai", pattern=r"ask ai (.+)")
    def on_ask_ai(ctx: dict):
        import re
        m = re.search(r"ask ai (.+)", ctx["matched_text"], re.IGNORECASE)
        question = m.group(1) if m else ctx["matched_text"]
        print(f"  [AI] Question: {question!r}")
        if ai is None:
            print("  [AI] (No API key — skipping real call)")
            return
        try:
            resp = ai.chat(question)
            print(f"  [AI] Answer: {resp.text}")
            # In a real app you would send resp.text to the glasses speaker via TTS.
        except MetaAIError as exc:
            print(f"  [AI ERROR] {exc}")

    handler.start()

    # Simulate a query
    print("--- Simulating: 'hey meta, ask ai what time is it in Tokyo' ---")
    handler.dispatch("hey meta, ask ai what time is it in Tokyo")

    handler.stop()
    glasses.disconnect()


if __name__ == "__main__":
    main()
