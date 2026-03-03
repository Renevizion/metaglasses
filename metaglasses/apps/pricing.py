"""
PricingApp — look up prices for products seen through the glasses.

Workflow
--------
1. The user says **"hey meta, price check <product>"** *or* takes a photo and
   says **"hey meta, price this"**.
2. The app sends the product name (or a vision query on the captured image) to
   Meta AI and returns the price information.
3. The result is stored in :attr:`PricingApp.last_result` and passed to an
   optional ``on_result`` callback.

Typical usage::

    from metaglasses import Glasses, MetaAIClient
    from metaglasses.apps.pricing import PricingApp

    glasses = Glasses()
    glasses.connect()
    ai = MetaAIClient(api_key="...", system_prompt=(
        "You are a pricing assistant. When asked for the price of a product, "
        "give the current typical retail price in USD, a brief reason, and "
        "where to buy it cheaply. Be concise."
    ))

    app = PricingApp(glasses, ai, on_result=lambda r: print(r["answer"]))
    app.start()
    app.price_check("Sony WH-1000XM5 headphones")  # programmatic
    app.stop()
    glasses.disconnect()
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from ..apps import App
from ..voice import VoiceCommandHandler


class PricingApp(App):
    """Voice-activated product price lookup powered by Meta AI.

    Parameters
    ----------
    glasses:
        A connected :class:`~metaglasses.glasses.Glasses` instance.
    ai:
        A :class:`~metaglasses.ai.MetaAIClient`.
    on_result:
        Optional callback invoked with a ``dict`` containing ``"query"``
        and ``"answer"`` keys whenever a price result is ready.
    """

    name = "pricing"
    description = "Look up prices for products via voice or camera"

    _SYSTEM_PROMPT = (
        "You are a pricing assistant. When asked for the price of a product, "
        "provide the current typical retail price range in USD, note whether "
        "it is a good deal, and suggest where to buy it cheaply. Be concise "
        "— no more than 3 sentences."
    )

    def __init__(
        self,
        glasses,
        ai=None,
        on_result: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(glasses, ai)
        self.on_result = on_result
        self.last_result: Optional[dict] = None

        # Apply a focused system prompt if the client has none yet
        if self.ai and not any(m.role == "system" for m in self.ai.history):
            from ..ai import Message
            self.ai._history.insert(0, Message(role="system", content=self._SYSTEM_PROMPT))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def price_check(self, product: str) -> dict:
        """Look up the price of *product* and return the result.

        Parameters
        ----------
        product:
            Product name or description (e.g. ``"Sony WH-1000XM5"``).

        Returns
        -------
        dict
            ``{"query": product, "answer": "<AI response text>"}``

        Raises
        ------
        RuntimeError
            If no AI client was provided.
        """
        if self.ai is None:
            raise RuntimeError("PricingApp requires an AI client (ai= argument).")
        response = self.ai.chat(f"What is the current price of: {product}?")
        result = {"query": product, "answer": response.text}
        self.last_result = result
        if self.on_result:
            self.on_result(result)
        return result

    def price_from_image(self, image_bytes: bytes) -> dict:
        """Identify and price the product visible in *image_bytes*.

        Parameters
        ----------
        image_bytes:
            Raw JPEG bytes captured by :meth:`~metaglasses.glasses.Glasses.take_photo`.

        Returns
        -------
        dict
            ``{"query": "<identified product>", "answer": "<AI response text>"}``
        """
        if self.ai is None:
            raise RuntimeError("PricingApp requires an AI client (ai= argument).")
        response = self.ai.describe_image(
            image_bytes,
            prompt=(
                "Identify the main product in this image and provide its "
                "current typical retail price in USD, whether it is a good "
                "deal, and where to buy it cheaply. Be concise."
            ),
        )
        result = {"query": "(from camera)", "answer": response.text}
        self.last_result = result
        if self.on_result:
            self.on_result(result)
        return result

    # ------------------------------------------------------------------
    # App internals
    # ------------------------------------------------------------------

    def _register_commands(self, handler: VoiceCommandHandler) -> None:
        handler.register(
            "price check",
            self._handle_price_check,
            pattern=r"price\s+(check|this|it)\s*(.*)",
        )

    def _handle_price_check(self, ctx: dict) -> None:
        text = ctx["matched_text"]
        m = re.search(r"price\s+(?:check|this|it)\s*(.*)", text, re.IGNORECASE)
        product = m.group(1).strip() if m and m.group(1).strip() else "the item in front of me"
        self.price_check(product)
