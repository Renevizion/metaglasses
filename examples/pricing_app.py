"""
Example: Price-check products by voice or camera.

    META_AI_API_KEY=<key> python examples/pricing_app.py
"""

import os

from metaglasses import Glasses, MetaAIClient, GlassesConnectionError
from metaglasses.apps.pricing import PricingApp


def main():
    api_key = os.environ.get("META_AI_API_KEY", "demo")

    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    ai = MetaAIClient(api_key=api_key)
    app = PricingApp(glasses, ai, on_result=lambda r: print(f"  💰 {r['query']}: {r['answer']}"))
    app.start()

    # Programmatic price check
    if api_key != "demo":
        print("Checking price for: Sony WH-1000XM5")
        app.price_check("Sony WH-1000XM5 headphones")
    else:
        print("[demo mode] Skipping real AI call.")

    # Voice command simulation
    print("\nSimulating: 'hey meta, price check AirPods Pro'")
    app._handler.dispatch("hey meta, price check AirPods Pro")

    app.stop()
    glasses.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
