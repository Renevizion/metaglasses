"""
Example: Research any topic via voice.

    META_AI_API_KEY=<key> python examples/research_app.py
"""

import os

from metaglasses import Glasses, MetaAIClient, GlassesConnectionError
from metaglasses.apps.research import ResearchApp


def main():
    api_key = os.environ.get("META_AI_API_KEY", "demo")

    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    ai = MetaAIClient(api_key=api_key)
    app = ResearchApp(glasses, ai, on_result=lambda r: print(f"\n📚 {r['topic']}\n{r['summary']}\n"))
    app.start()

    # Voice command simulations
    print("Simulating: 'hey meta, research quantum computing'")
    app._handler.dispatch("hey meta, research quantum computing")

    print("Simulating: 'hey meta, tell me more about qubits'")
    app._handler.dispatch("hey meta, tell me more about qubits")

    app.stop()
    glasses.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
