"""
Example: Rapidly spin up specialized apps with QuickApp — no subclassing needed.

Demonstrates building several specialized apps in just a few lines each,
all running simultaneously on the same glasses.

    META_AI_API_KEY=<key> python examples/quick_apps.py
"""

import os

from metaglasses import Glasses, MetaAIClient, AppRunner, GlassesConnectionError
from metaglasses.apps.factory import QuickApp, quick_app


def main():
    api_key = os.environ.get("META_AI_API_KEY", "demo")

    glasses = Glasses()
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    ai = MetaAIClient(api_key=api_key) if api_key != "demo" else None

    # ── 1. Nutrition assistant ───────────────────────────────────────────────
    nutrition = (
        QuickApp(
            "nutrition",
            "Calorie & nutrition info for food you see or mention",
            ai_system_prompt=(
                "You are a certified nutritionist. Give concise answers: "
                "calories, macros, and one health tip. Max 3 sentences."
            ),
            on_result=lambda r: print(f"  🥗 [nutrition] {r}"),
        )
        .on(
            r"(?:calories|nutrition|how healthy is|macros for)\s+(.+)",
            lambda ctx, app: app.ask_ai(f"Nutrition info for: {ctx['groups'][0]}"),
        )
        .on(
            r"is .+ (?:healthy|good for me)",
            lambda ctx, app: app.ask_ai(ctx["matched_text"]),
        )
    )

    # ── 2. Wine sommelier ────────────────────────────────────────────────────
    wine = (
        QuickApp(
            "wine",
            "Sommelier — wine pairings and recommendations",
            ai_system_prompt=(
                "You are a world-class sommelier. Recommend wines concisely: "
                "name, region, why it pairs well. Max 2-3 sentences."
            ),
            on_result=lambda r: print(f"  🍷 [wine] {r}"),
        )
        .on(
            r"(?:recommend|suggest|pair)\s+(?:a\s+)?wine\s*(.*)",
            lambda ctx, app: app.ask_ai(
                f"Recommend a wine for: {ctx['groups'][0] or 'dinner'}"
            ),
        )
        .on(
            r"what wine (?:goes|pairs) with\s+(.+)",
            lambda ctx, app: app.ask_ai(f"Wine pairing for: {ctx['groups'][0]}"),
        )
    )

    # ── 3. Fitness coach ─────────────────────────────────────────────────────
    fitness = (
        QuickApp(
            "fitness",
            "On-the-spot workout and fitness coaching",
            ai_system_prompt=(
                "You are a certified personal trainer. Give quick, actionable "
                "advice. Max 3 sentences."
            ),
            on_result=lambda r: print(f"  💪 [fitness] {r}"),
        )
        .on(
            r"(?:workout|exercise|workout for)\s+(.+)",
            lambda ctx, app: app.ask_ai(
                f"Quick workout suggestion for: {ctx['groups'][0]}"
            ),
        )
        .on(
            r"how (?:do i|to)\s+(.+)",
            lambda ctx, app: app.ask_ai(
                f"Explain how to do this exercise: {ctx['groups'][0]}"
            ),
        )
    )

    # ── 4. Stock ticker ──────────────────────────────────────────────────────
    stocks = quick_app(
        "stocks",
        "Real-time stock price and market info",
        ai_system_prompt=(
            "You are a financial assistant. Give stock price ranges, "
            "1-day change, and one insight. Max 2 sentences."
        ),
        on_result=lambda r: print(f"  📈 [stocks] {r}"),
    ).on(
        r"(?:price of|stock|ticker|how is)\s+([A-Za-z]+)",
        lambda ctx, app: app.ask_ai(
            f"Current stock price and 1-day change for {ctx['groups'][0]}"
        ),
    )

    # ── 5. Language translator ───────────────────────────────────────────────
    translator = (
        QuickApp(
            "translator",
            "Instant language translation",
            ai_system_prompt=(
                "You are a translator. Translate the given text to the "
                "requested language. Return only the translation."
            ),
            on_result=lambda r: print(f"  🌍 [translator] {r}"),
        )
        .on(
            r"translate (.+) to (\w+)",
            lambda ctx, app: app.ask_ai(
                f"Translate '{ctx['groups'][0]}' to {ctx['groups'][1]}"
            ),
        )
        .on(
            r"how do you say (.+) in (\w+)",
            lambda ctx, app: app.ask_ai(
                f"How do you say '{ctx['groups'][0]}' in {ctx['groups'][1]}?"
            ),
        )
    )

    # ── Register and launch all apps at once ─────────────────────────────────
    runner = AppRunner(glasses, ai)
    for app in [nutrition, wine, fitness, stocks, translator]:
        runner.register(app)

    print("Registered apps:")
    for info in runner.list_apps():
        print(f"  • {info['name']:12s} — {info['description']}")

    print("\nLaunching all apps…")
    for info in runner.list_apps():
        runner.launch(info["name"])

    # ── Simulate voice commands for each app ─────────────────────────────────
    print("\n── Voice command simulations ──\n")
    sims = [
        ("hey meta, calories in a Big Mac",                   "nutrition"),
        ("hey meta, recommend a wine for steak",              "wine"),
        ("hey meta, workout for abs",                         "fitness"),
        ("hey meta, stock AAPL",                              "stocks"),
        ("hey meta, translate hello world to Spanish",        "translator"),
        ("hey meta, how do you say thank you in Japanese",    "translator"),
    ]
    for utterance, app_name in sims:
        print(f"  [{app_name}] '{utterance}'")
        runner._apps[app_name]._handler.dispatch(utterance)

    runner.stop_all()
    glasses.disconnect()
    print("\nAll apps stopped. Done.")


if __name__ == "__main__":
    main()
