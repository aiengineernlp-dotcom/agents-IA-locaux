"""Mini-framework d'agent : boucle LLM <-> outils, sans dépendance lourde.

Un agent = un modèle Ollama + un prompt système + des fonctions Python (outils).
Le modèle décide quand appeler un outil, on exécute la fonction, on lui renvoie
le résultat, et ainsi de suite jusqu'à la réponse finale.
"""
from __future__ import annotations

import json
from typing import Callable

import ollama

from .config import NUM_CTX, OLLAMA_HOST

client = ollama.Client(host=OLLAMA_HOST)
MAX_TOOL_OUTPUT = 6000  # caractères renvoyés au modèle par appel d'outil


class Agent:
    def __init__(
        self,
        name: str,
        model: str,
        system: str,
        tools: list[Callable] | None = None,
        temperature: float = 0.2,
        max_steps: int = 8,
        verbose: bool = True,
    ):
        self.name = name
        self.model = model
        self.system = system
        self.tools = list(tools or [])
        self.registry = {t.__name__: t for t in self.tools}
        self.temperature = temperature
        self.max_steps = max_steps
        self.verbose = verbose
        self.use_tools = bool(self.tools)
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.messages: list = [{"role": "system", "content": self.system}]

    def _log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def _chat(self):
        kwargs = dict(
            model=self.model,
            messages=self.messages,
            options={"temperature": self.temperature, "num_ctx": NUM_CTX},
        )
        if self.use_tools:
            kwargs["tools"] = self.tools
        try:
            return client.chat(**kwargs)
        except ollama.ResponseError as e:
            # Certains modèles (ex. deepseek-r1) ne gèrent pas les outils : on bascule en texte seul.
            if self.use_tools and "tool" in str(e).lower():
                self._log("⚠️  Ce modèle ne gère pas les outils → mode texte seul.")
                self.use_tools = False
                kwargs.pop("tools")
                return client.chat(**kwargs)
            raise

    def _execute(self, name: str, args: dict) -> str:
        fn = self.registry.get(name)
        if fn is None:
            return f"Erreur : outil inconnu '{name}'. Outils disponibles : {list(self.registry)}"
        try:
            out = fn(**args)
        except TypeError as e:
            return f"Erreur d'arguments pour {name} : {e}"
        except Exception as e:  # l'agent doit pouvoir lire l'erreur et se corriger
            return f"Erreur dans {name} : {type(e).__name__}: {e}"
        if not isinstance(out, str):
            out = json.dumps(out, ensure_ascii=False, indent=2, default=str)
        if len(out) > MAX_TOOL_OUTPUT:
            out = out[:MAX_TOOL_OUTPUT] + "\n…[résultat tronqué]"
        return out

    # ------------------------------------------------------------------
    def ask(self, text: str) -> str:
        """Envoie un message, exécute les outils demandés, renvoie la réponse finale."""
        self.messages.append({"role": "user", "content": text})
        for _ in range(self.max_steps):
            resp = self._chat()
            msg = resp.message
            self.messages.append(msg)
            if not msg.tool_calls:
                return msg.content or ""
            for call in msg.tool_calls:
                name = call.function.name
                args = dict(call.function.arguments or {})
                self._log(f"🔧 {name}({json.dumps(args, ensure_ascii=False)[:160]})")
                result = self._execute(name, args)
                self.messages.append({"role": "tool", "tool_name": name, "content": result})
        return "⚠️ Limite d'étapes atteinte avant la réponse finale. Reformule ou découpe la tâche."

    def chat(self) -> None:
        """Boucle interactive dans le terminal."""
        print(f"💬 {self.name}  (modèle : {self.model})   /reset = oublier · /quit = sortir")
        while True:
            try:
                q = input("\nvous › ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not q:
                continue
            if q in ("/quit", "/exit"):
                break
            if q == "/reset":
                self.reset()
                print("↺ contexte vidé")
                continue
            print("\n" + self.ask(q))


def structured(model: str, system: str, prompt: str, schema: dict, temperature: float = 0.4) -> dict:
    """Sortie JSON garantie par un schéma (beaucoup plus fiable que les outils avec un petit modèle)."""
    resp = client.chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        format=schema,
        options={"temperature": temperature, "num_ctx": NUM_CTX},
    )
    return json.loads(resp.message.content)
