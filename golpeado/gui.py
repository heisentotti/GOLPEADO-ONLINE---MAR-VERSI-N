from __future__ import annotations

import os
import random
import subprocess
import sys
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .game import Game, GameOver, GameState, InvalidMove, TurnPhase
from .models import Card, PlayerType, Suit
from .bots import Difficulty
from .solo import SoloConfig, SoloSession
from .mixed import MixedConfig, MixedSession

# Palette: restrained felt / ivory / brass. No game rules live here.
BG = "#0b1714"
TABLE = "#17483d"
TABLE_DARK = "#10382f"
PANEL = "#10241f"
PANEL_2 = "#15332b"
GOLD = "#d6b45f"
GOLD_SOFT = "#e9d18a"
TEXT = "#f5f0e5"
MUTED = "#a9bbb5"
CARD_BG = "#fbf8ef"
CARD_EDGE = "#d9d2c2"
CARD_SELECTED = "#f0d879"
RED = "#b83a43"
DARK = "#17201d"
SUCCESS = "#82c99c"
DANGER = "#d97878"
SHADOW = "#0a1110"

FONT = "DejaVu Sans"


class CardView(tk.Frame):
    """Clickable physical-card representation. It contains no game logic."""

    def __init__(self, master, card: Card, command, selected=False, small=False):
        self.card = card
        self.command = command
        self.selected = selected
        self.small = small
        width, height = ((56, 76) if small else (74, 104))
        bg = CARD_SELECTED if selected else CARD_BG
        super().__init__(
            master,
            bg=bg,
            width=width,
            height=height,
            highlightthickness=2 if selected else 1,
            highlightbackground=GOLD if selected else CARD_EDGE,
            highlightcolor=GOLD,
            cursor="hand2",
        )
        self.pack_propagate(False)
        self._base_bg = bg
        self._hover_bg = "#fffdf7" if not selected else CARD_SELECTED
        color = RED if card.suit in (Suit.HEARTS, Suit.DIAMONDS) else DARK
        rank_font = (FONT, 13 if small else 17, "bold")
        suit_font = (FONT, 16 if small else 22, "bold")
        tk.Label(self, text=card.rank.label, bg=bg, fg=color, font=rank_font).pack(anchor="nw", padx=7, pady=(5, 0))
        tk.Label(self, text=card.suit.symbol, bg=bg, fg=color, font=suit_font).pack(expand=True)
        tk.Label(self, text=card.rank.label, bg=bg, fg=color, font=(FONT, 9 if small else 11, "bold")).pack(anchor="se", padx=7, pady=(0, 5))
        self._bind_recursive(self, self._click)
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _bind_recursive(self, widget, callback):
        widget.bind("<Button-1>", callback, add="+")
        for child in widget.winfo_children():
            self._bind_recursive(child, callback)

    def _click(self, _event=None):
        self.command(self.card)

    def _set_bg(self, color):
        self.configure(bg=color)
        for child in self.winfo_children():
            try:
                child.configure(bg=color)
            except tk.TclError:
                pass

    def _enter(self, _event=None):
        if not self.selected:
            self._set_bg(self._hover_bg)
            self.lift()

    def _leave(self, _event=None):
        self._set_bg(self._base_bg)


class GolpeadoApp(tk.Tk):
    """Desktop UI over the authoritative Game engine."""

    def __init__(self):
        super().__init__()
        self.title("Golpeado Online")
        self.geometry("1360x860")
        self.minsize(1040, 700)
        self.configure(bg=BG)
        self.session: Optional[object] = None
        self.game: Optional[Game] = None
        self.human_id = "human"
        self.selected: set[str] = set()
        self.hand_order: list[str] = []
        self.mode = "solo"
        self.bot_job = None
        self.bot_count = 3
        self.difficulty = Difficulty.NORMAL
        self.message = ""
        self.status_var = tk.StringVar(value="")
        self._victory_overlay = None
        self.bind("<Escape>", lambda _e: self.selected.clear() or self.render())
        self.bind("<KeyPress-r>", self._key_sort)
        self.bind("<KeyPress-R>", self._key_sort)
        self.bind("<KeyPress-d>", self._key_discard)
        self.bind("<KeyPress-D>", self._key_discard)
        self.bind("<KeyPress-space>", self._key_primary)
        self.show_menu()

    def _key_sort(self, _event=None):
        if self.game:
            self.sort_hand()

    def _key_discard(self, _event=None):
        if self.game and len(self.selected) == 1:
            self.discard_card()

    def _key_primary(self, _event=None):
        if not self.game or self.game.current_player.id != self.human_id:
            return
        if self.game.phase == TurnPhase.DRAW:
            self.draw_card()
        elif self.game.phase == TurnPhase.DISCARD and len(self.selected) == 1:
            self.discard_card()

    def clear(self):
        if self.bot_job is not None:
            try:
                self.after_cancel(self.bot_job)
            except tk.TclError:
                pass
            self.bot_job = None
        for child in self.winfo_children():
            child.destroy()
        self._victory_overlay = None

    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=GOLD)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)])

    def _button(self, parent, text, command, primary=False, width=None):
        kwargs = dict(
            text=text,
            command=command,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=9,
            font=(FONT, 10, "bold"),
            bg=GOLD if primary else PANEL_2,
            fg=DARK if primary else TEXT,
            activebackground=GOLD_SOFT if primary else "#20473c",
            activeforeground=DARK if primary else TEXT,
        )
        if width:
            kwargs["width"] = width
        return tk.Button(parent, **kwargs)

    def show_menu(self):
        self.clear()
        self._style()
        outer = tk.Frame(self, bg=BG)
        outer.pack(expand=True, fill="both")

        hero = tk.Frame(outer, bg=BG)
        hero.pack(pady=(55, 20))
        tk.Label(hero, text="GOLPEADO", bg=BG, fg=GOLD, font=(FONT, 42, "bold")).pack()
        tk.Label(hero, text="Una mesa. Una baraja. Tu turno.", bg=BG, fg=TEXT, font=(FONT, 15)).pack(pady=(5, 0))

        box = tk.Frame(outer, bg=PANEL, padx=38, pady=30,
                       highlightthickness=1, highlightbackground="#21463d")
        box.pack(padx=24)
        box.grid_columnconfigure(1, minsize=260)

        tk.Label(box, text="PARTIDA LOCAL", bg=PANEL, fg=GOLD,
                 font=(FONT, 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        labels = ["Modo", "Jugadores totales", "Dificultad de bots"]
        for i, label in enumerate(labels, start=1):
            tk.Label(box, text=label, bg=PANEL, fg=TEXT,
                     font=(FONT, 11, "bold")).grid(row=i, column=0, sticky="w", pady=8)

        self.mode_var = tk.StringVar(value="Solo vs bots")
        ttk.Combobox(
            box, textvariable=self.mode_var,
            values=("Solo vs bots", "Mixto"),
            state="readonly", font=(FONT, 11)
        ).grid(row=1, column=1, sticky="ew", padx=(25, 0), pady=4)

        self.count_var = tk.IntVar(value=4)
        spin = tk.Spinbox(
            box, from_=2, to=4, textvariable=self.count_var, width=8,
            font=(FONT, 12), buttonbackground=PANEL_2, relief="flat"
        )
        spin.grid(row=2, column=1, sticky="w", padx=(25, 0), pady=4)

        self.diff_var = tk.StringVar(value="Normal")
        ttk.Combobox(
            box, textvariable=self.diff_var,
            values=("Fácil", "Normal", "Difícil", "Experto"),
            state="readonly", font=(FONT, 11)
        ).grid(row=3, column=1, sticky="ew", padx=(25, 0), pady=4)

        buttons = tk.Frame(box, bg=PANEL)
        buttons.grid(row=4, column=0, columnspan=2, pady=(25, 2))

        self._button(
            buttons, "JUGAR", self.start_game, primary=True, width=15
        ).pack(side="left", padx=5)

        self._button(
            buttons, "JUGAR ONLINE", self.open_online, primary=False, width=15
        ).pack(side="left", padx=5)

        self.online_status = tk.Label(
            outer,
            text="Online abre la mesa web en tu navegador.",
            bg=BG, fg=MUTED, font=(FONT, 9)
        )
        self.online_status.pack(pady=(15, 4))

        tk.Label(
            outer,
            text="El motor central controla todas las reglas y validaciones.",
            bg=BG, fg=MUTED, font=(FONT, 9)
        ).pack(pady=4)

    def open_online(self):
        """Open the online lobby. Uses a deployed URL when configured; otherwise starts the local server."""
        url = os.environ.get("GOLPEADO_ONLINE_URL", "").strip()

        if not url:
            url = "http://127.0.0.1:8000"
            process = getattr(self, "_online_process", None)

            if process is None or process.poll() is not None:
                try:
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    self._online_process = subprocess.Popen(
                        [
                            sys.executable, "-m", "uvicorn",
                            "golpeado.server:app",
                            "--host", "127.0.0.1",
                            "--port", "8000",
                        ],
                        cwd=project_root,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as exc:
                    self.online_status.config(
                        text=f"No se pudo iniciar el servidor online: {exc}",
                        fg=DANGER
                    )
                    return

            # Give uvicorn a moment to bind before opening the browser.
            self.after(700, lambda: webbrowser.open(url))
        else:
            webbrowser.open(url)

    def start_game(self):
        total = max(2, min(4, int(self.count_var.get())))
        difficulty = {"Fácil": Difficulty.EASY, "Normal": Difficulty.NORMAL, "Difícil": Difficulty.HARD, "Experto": Difficulty.EXPERT}[self.diff_var.get()]
        seed = random.randrange(1 << 30)
        if self.mode_var.get() == "Mixto":
            bot_count = total - 1
            self.session = MixedSession(MixedConfig(1, bot_count, difficulty, seed=seed), ["Mar"])
        else:
            bot_count = total - 1
            self.session = SoloSession(SoloConfig(bot_count=bot_count, difficulty=difficulty, seed=seed))
        self.game = self.session.game
        self.human_id = next(p.id for p in self.game.players if p.type == PlayerType.HUMAN)
        me = next(p for p in self.game.players if p.id == self.human_id)
        self.selected.clear()
        self.hand_order = [c.id for c in me.hand]
        self.message = "Tu turno: roba una carta o recoge el último descarte."
        self.show_table()
        self.schedule_bots()

    def show_table(self):
        self.clear()
        self._style()
        self.table = tk.Frame(self, bg=TABLE)
        self.table.pack(expand=True, fill="both")

        header = tk.Frame(self.table, bg=PANEL, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="GOLPEADO", bg=PANEL, fg=GOLD, font=(FONT, 19, "bold")).pack(side="left", padx=22)
        self.turn_label = tk.Label(header, text="", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold"))
        self.turn_label.pack(side="left", padx=24)
        self.phase_label = tk.Label(header, text="", bg=PANEL, fg=MUTED, font=(FONT, 10))
        self.phase_label.pack(side="left")
        self._button(header, "SALIR AL MENÚ", self.show_menu).pack(side="right", padx=16)

        self.opponents = tk.Frame(self.table, bg=TABLE)
        self.opponents.pack(fill="x", padx=24, pady=(15, 8))

        self.middle = tk.Frame(self.table, bg=TABLE)
        self.middle.pack(expand=True, fill="both", padx=24)
        self.left = tk.Frame(self.middle, bg=TABLE, width=185)
        self.left.pack(side="left", fill="y", padx=(0, 18))
        self.center = tk.Frame(self.middle, bg=TABLE)
        self.center.pack(side="left", expand=True, fill="both")
        self.right = tk.Frame(self.middle, bg=TABLE, width=150)
        self.right.pack(side="right", fill="y", padx=(18, 0))

        self.hand_frame = tk.Frame(self.table, bg=TABLE)
        self.hand_frame.pack(fill="x", padx=24, pady=(8, 7))
        self.action_bar = tk.Frame(self.table, bg=PANEL, height=62)
        self.action_bar.pack(fill="x", side="bottom")
        self.action_bar.pack_propagate(False)

        self.render()

    def _panel(self, parent, title, subtitle=None):
        frame = tk.Frame(parent, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#285448")
        tk.Label(frame, text=title, bg=PANEL, fg=GOLD, font=(FONT, 9, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(frame, text=subtitle, bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(anchor="w", pady=(2, 0))
        return frame

    def _remove_render_body(self, body):
        if body is not getattr(self, "_render_body", None) and body.winfo_exists():
            body.destroy()

    def _clear_children(self, frame):
        for child in frame.winfo_children():
            child.destroy()

    def _set_label(self, parent, key, text, **kwargs):
        widget=getattr(self, key, None)
        if widget is None or not widget.winfo_exists():
            widget=tk.Label(parent, **kwargs)
            setattr(self, key, widget)
        widget.config(text=text, **{k:v for k,v in kwargs.items() if k in ("fg","bg","font")})

    def render(self):
        if not self.game:
            return

        g = self.game
        current = g.current_player
        me = next(p for p in g.players if p.id == self.human_id)

        # Keep the main containers alive. Only their contents are refreshed.
        self._clear_children(self.opponents)
        self._clear_children(self.center)
        self._clear_children(self.left)
        self._clear_children(self.right)
        self._clear_children(self.hand_frame)
        self._clear_children(self.action_bar)

        self.turn_label.config(
            text=f"TURNO {g.turn_number}  ·  {current.name}",
            fg=GOLD if current.id == self.human_id else TEXT
        )
        phase_text = {
            TurnPhase.DRAW: "Obtener 1 carta",
            TurnPhase.ACTION: "Acción / grupo",
            TurnPhase.DISCARD: "Descartar 1"
        }.get(g.phase, "")
        self.phase_label.config(text=phase_text)

        rivals = [p for p in g.players if p.id != self.human_id]
        for p in rivals:
            card = tk.Frame(
                self.opponents, bg=PANEL, padx=14, pady=8, highlightthickness=1,
                highlightbackground=GOLD if p.id == current.id else "#285448"
            )
            card.pack(side="left", expand=True, fill="x", padx=4)
            active_text = "  TU TURNO" if p.id == current.id else ""
            tk.Label(card, text=p.name + active_text, bg=PANEL,
                     fg=GOLD if p.id == current.id else TEXT,
                     font=(FONT, 11, "bold")).pack(anchor="w")
            tk.Label(card, text=f"{len(p.hand)} cartas  ·  " +
                     ("grupo bajado" if p.lowered_group else "sin grupo"),
                     bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(2, 0))
            if p.lowered_group:
                row = tk.Frame(card, bg=PANEL)
                row.pack(anchor="w", pady=(6, 0))
                for c in p.lowered_group.cards:
                    CardView(row, c, lambda _: None, small=True).pack(side="left", padx=2)

        tk.Label(self.center, text=self.message, bg=TABLE, fg=TEXT,
                 font=(FONT, 12, "bold")).pack(pady=(17, 8))
        piles = tk.Frame(self.center, bg=TABLE)
        piles.pack(expand=True)

        can_act = g.state == GameState.PLAYING and current.id == self.human_id
        deckbox = self._panel(piles, "MAZO", f"{len(g.deck.cards)} cartas")
        deckbox.pack(side="left", padx=16, pady=8)
        deck_btn = self._button(deckbox, "▣\nROBAR", self.draw_card,
                                primary=can_act and g.phase == TurnPhase.DRAW)
        deck_btn.config(font=(FONT, 15, "bold"), width=8, height=2)
        deck_btn.pack(pady=(8, 4))

        discardbox = self._panel(piles, "ÚLTIMO DESCARTE", "Solo esta carta puede recogerse")
        discardbox.pack(side="left", padx=16, pady=8)
        last = g.last_discard
        if last:
            CardView(discardbox, last,
                     lambda c: self._discard_hint() if can_act else None).pack(pady=(8, 4))
        else:
            tk.Label(discardbox, text="—\nVACÍO", bg=PANEL_2, fg=MUTED,
                     width=11, height=4, font=(FONT, 12, "bold")).pack(pady=(8, 4))

        info = self._panel(piles, "TU ESTADO", f"{len(me.hand)} cartas en mano")
        info.pack(side="left", padx=16, pady=8)
        tk.Label(info, text="GRUPO: " + ("BAJADO" if me.lowered_group else "NO BAJADO"),
                 bg=PANEL, fg=SUCCESS if me.lowered_group else MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(10, 3))
        tk.Label(info, text="ENCHUFE: " + ("PRIVADO" if me.plug else "NINGUNO"),
                 bg=PANEL, fg=GOLD if me.plug else MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w")

        if me.lowered_group:
            group = self._panel(self.left, "TU GRUPO BAJADO", "Público")
            group.pack(fill="x")
            row = tk.Frame(group, bg=PANEL)
            row.pack(pady=(7, 0))
            for c in me.lowered_group.cards:
                CardView(row, c, lambda _: None, small=True).pack(side="left", padx=2)
        else:
            self._panel(self.left, "GRUPO BAJADO", "Todavía puedes bajar uno").pack(fill="x")

        private = self._panel(self.left, "ENCHUFE", "Información privada")
        private.pack(fill="x", pady=(10, 0))
        tk.Label(private, text="PRIVADO" if me.plug else "NINGUNO", bg=PANEL,
                 fg=GOLD if me.plug else MUTED,
                 font=(FONT, 10, "bold")).pack(pady=(7, 0))

        helpbox = self._panel(self.right, "ATAJOS", "Teclado")
        helpbox.pack(fill="x")
        for line in ("ESPACIO  obtener", "D  descartar", "R  ordenar", "ESC  limpiar selección"):
            tk.Label(helpbox, text=line, bg=PANEL, fg=MUTED,
                     font=(FONT, 8), anchor="w").pack(fill="x", pady=2)

        hand_header = tk.Frame(self.hand_frame, bg=TABLE)
        hand_header.pack(fill="x")
        tk.Label(hand_header, text=f"TU MANO  ·  {len(me.hand)} CARTAS", bg=TABLE,
                 fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
        tk.Label(hand_header, text=f"Seleccionadas: {len(self.selected)}", bg=TABLE,
                 fg=GOLD, font=(FONT, 9, "bold")).pack(side="right")
        row = tk.Frame(self.hand_frame, bg=TABLE)
        row.pack(fill="x", pady=(6, 4))
        cards_by_id = {c.id: c for c in me.hand}
        ordered_ids = [cid for cid in self.hand_order if cid in cards_by_id]
        ordered_ids += [c.id for c in me.hand if c.id not in ordered_ids]
        self.hand_order = ordered_ids
        for cid in ordered_ids:
            CardView(row, cards_by_id[cid], self.toggle_card, cid in self.selected).pack(side="left", padx=3)

        if can_act:
            if g.phase == TurnPhase.DRAW:
                self._button(self.action_bar, "ROBAR  [ESPACIO]", self.draw_card, primary=True).pack(
                    side="left", padx=(18, 7), pady=9)
                take_enabled = last is not None and len(self.selected) in (2, 3) and last.id not in self.selected
                self._button(self.action_bar, "RECOGER DESCARTE", self.take_discard,
                             primary=take_enabled).pack(side="left", padx=7, pady=9)
            elif g.phase == TurnPhase.ACTION:
                lower_enabled = me.lowered_group is None and len(self.selected) in (3, 4)
                self._button(self.action_bar, "BAJAR GRUPO", self.lower_group,
                             primary=lower_enabled).pack(side="left", padx=(18, 7), pady=9)
                self._button(self.action_bar, "DESCARTAR [D]", self.discard_card,
                             primary=len(self.selected) == 1).pack(side="left", padx=7, pady=9)
            elif g.phase == TurnPhase.DISCARD:
                self._button(self.action_bar, "DESCARTAR [D]", self.discard_card,
                             primary=len(self.selected) == 1).pack(side="left", padx=(18, 7), pady=9)
        else:
            tk.Label(self.action_bar, text=f"Esperando a {current.name}…", bg=PANEL,
                     fg=MUTED, font=(FONT, 10, "bold")).pack(side="left", padx=20)

        self._button(self.action_bar, "ORDENAR [R]", self.sort_hand).pack(side="right", padx=7, pady=9)
        self._button(self.action_bar, "NUEVA PARTIDA", self.show_menu).pack(
            side="right", padx=(7, 16), pady=9)

    def _discard_hint(self):
        self.message = "El último descarte se recoge solo como alternativa al robo y debe completar un grupo."
        self.render()

    def toggle_card(self, card: Card):
        if not self.game or self.game.current_player.id != self.human_id or self.game.phase not in (TurnPhase.DRAW, TurnPhase.ACTION, TurnPhase.DISCARD):
            return
        if card.id in self.selected:
            self.selected.remove(card.id)
        else:
            self.selected.add(card.id)
        self.render()

    def draw_card(self):
        if not self.game:
            return
        try:
            self.game.draw(self.human_id)
            self.selected.clear()
            self.message = "Carta obtenida. Ahora puedes bajar un grupo o descartar una carta."
            self.render()
        except (InvalidMove, GameOver) as e:
            self.messagebox_info("Movimiento no válido", str(e))
            self.render()

    def lower_group(self):
        self._perform(lambda: self.game.lower_group(self.human_id, tuple(self.selected)), "Grupo bajado. Ahora debes descartar una carta.")

    def take_discard(self):
        last = self.game.last_discard if self.game else None
        if not last:
            return
        ids = tuple(self.selected) + (last.id,)
        self._perform(lambda: self.game.take_last_discard(self.human_id, ids), "Recogiste el descarte y bajaste el grupo. Ahora debes descartar una carta.")

    def discard_card(self):
        if len(self.selected) != 1:
            return
        cid = next(iter(self.selected))
        self._perform(lambda: self.game.discard(self.human_id, cid), "Descarte realizado. Turno siguiente.")

    def _perform(self, fn, success):
        try:
            fn()
            self.selected.clear()
            self.message = success
            if self.game.state == GameState.WON:
                self.render()
                self.show_victory()
                return
            self.render()
            self.schedule_bots()
        except (InvalidMove, GameOver) as e:
            self.messagebox_info("Movimiento no válido", str(e))
            self.render()

    def sort_hand(self):
        if not self.game:
            return
        me = next(p for p in self.game.players if p.id == self.human_id)
        suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}
        self.hand_order = [c.id for c in sorted(me.hand, key=lambda c: (suit_order[c.suit], c.value))]
        self.render()

    def schedule_bots(self):
        if self.bot_job is not None:
            try:
                self.after_cancel(self.bot_job)
            except tk.TclError:
                pass
            self.bot_job = None
        if self.game and self.game.state == GameState.PLAYING and self.game.current_player.id != self.human_id:
            self.bot_job = self.after(500, self.process_one_bot_turn)

    def process_one_bot_turn(self):
        self.bot_job = None
        if not self.session or self.game is None or self.game.state != GameState.PLAYING:
            return
        if self.game.current_player.id == self.human_id:
            self.render()
            return
        pid = self.game.current_player.id
        try:
            self.message = f"{self.game.current_player.name} está pensando…"
            self.render()
            self.update_idletasks()
            self.session.play_next_bot()
            if self.game.state == GameState.WON:
                self.render()
                self.show_victory()
                return
            self.message = f"Turno de {self.game.current_player.name}."
            self.render()
            self.schedule_bots()
        except (InvalidMove, GameOver, RuntimeError, ValueError) as e:
            self.message = f"Error de sincronización del bot {pid}: {e}"
            self.render()

    def show_victory(self):
        if not self.game or not self.game.winner:
            return
        winner = next(p for p in self.game.players if p.id == self.game.winner.player_id)
        self._victory_overlay = tk.Frame(self, bg=BG)
        self._victory_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        panel = tk.Frame(self._victory_overlay, bg=PANEL, padx=48, pady=42, highlightthickness=1, highlightbackground=GOLD)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(panel, text="¡GOLPEADO!", bg=PANEL, fg=GOLD, font=(FONT, 30, "bold")).pack()
        tk.Label(panel, text=winner.name, bg=PANEL, fg=TEXT, font=(FONT, 21, "bold")).pack(pady=(10, 4))
        tk.Label(panel, text=f"{self.game.winner.reason}", bg=PANEL, fg=MUTED, font=(FONT, 10)).pack(pady=(0, 24))
        row = tk.Frame(panel, bg=PANEL)
        row.pack()
        self._button(row, "JUGAR DE NUEVO", self._restart_same, primary=True).pack(side="left", padx=5)
        self._button(row, "MENÚ", self.show_menu).pack(side="left", padx=5)

    def _restart_same(self):
        # Restart uses the same selected configuration; it does not alter rules.
        if self.mode_var.get() if hasattr(self, "mode_var") else False:
            self.start_game()
        else:
            self.show_menu()

    def messagebox_info(self, title, msg):
        messagebox.showinfo(title, msg)


def main():
    app = GolpeadoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
