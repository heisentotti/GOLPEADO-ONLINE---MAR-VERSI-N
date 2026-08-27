from __future__ import annotations

import tkinter as tk

from golpeado import GameState
from golpeado.gui import GolpeadoApp
from golpeado.solo import SoloConfig, SoloSession
from golpeado.bots import Difficulty


def test_solo_session_supports_1_2_3_bots():
    for count in (1, 2, 3):
        session = SoloSession(SoloConfig(count, Difficulty.NORMAL, seed=100 + count))
        assert len(session.game.players) == count + 1
        assert len(session.controllers) == count


def test_desktop_gui_complete_solo_game_against_bots(monkeypatch):
    monkeypatch.setattr("golpeado.gui.messagebox.showinfo", lambda *a, **k: None)
    app = GolpeadoApp()
    app.withdraw()
    session = SoloSession(SoloConfig(3, Difficulty.NORMAL, seed=1234))
    app.session = session
    app.game = session.game
    app.hand_order = [c.id for c in app.game.players[0].hand]
    app.message = "Tu turno"
    app.show_table()

    # A bot controller stands in for the human only in this automated UI test.
    from golpeado.bots import BotController
    human = BotController(Difficulty.HARD, seed=777)
    for _ in range(4000):
        app.update_idletasks()
        if app.game.state == GameState.WON:
            break
        if app.game.current_player.id == app.human_id:
            human.play_turn(app.game, app.human_id)
            app.selected.clear()
            app.render()
        else:
            session.play_next_bot()
            app.render()
    assert app.game.state == GameState.WON
    assert app.game.winner is not None
    app.destroy()
