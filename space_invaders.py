#!/usr/bin/env python3
"""A simple Space Invaders-style game using only tkinter (built into macOS Python)."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass


WIDTH = 800
HEIGHT = 600
BG = "#05070f"
FPS_MS = 16  # ~60 FPS


@dataclass
class Bullet:
    x: float
    y: float
    vy: float
    from_player: bool
    active: bool = True


@dataclass
class Invader:
    x: float
    y: float
    alive: bool = True


class SpaceInvaders:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Space Invaders (tkinter)")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack()

        self.left_pressed = False
        self.right_pressed = False
        self.fire_pressed = False

        self.player_w = 60
        self.player_h = 20
        self.player_x = WIDTH / 2
        self.player_y = HEIGHT - 40
        self.player_speed = 7
        self.player_lives = 3
        self.player_cooldown = 0

        self.invader_rows = 5
        self.invader_cols = 10
        self.invader_w = 40
        self.invader_h = 26
        self.invader_gap_x = 16
        self.invader_gap_y = 14
        self.invader_start_x = 90
        self.invader_start_y = 70
        self.invader_dx = 1.1
        self.invader_step_down = 20

        self.invaders: list[Invader] = []
        self.bullets: list[Bullet] = []
        self.enemy_fire_chance = 0.01

        self.score = 0
        self.level = 1
        self.running = True
        self.message = ""

        self.shields: list[tuple[float, float, float, float, int]] = []
        self._make_shields()
        self._make_invaders()

        self.root.bind("<KeyPress-Left>", lambda _: self._set_key("left", True))
        self.root.bind("<KeyRelease-Left>", lambda _: self._set_key("left", False))
        self.root.bind("<KeyPress-Right>", lambda _: self._set_key("right", True))
        self.root.bind("<KeyRelease-Right>", lambda _: self._set_key("right", False))
        self.root.bind("<KeyPress-space>", lambda _: self._set_key("fire", True))
        self.root.bind("<KeyRelease-space>", lambda _: self._set_key("fire", False))
        self.root.bind("r", lambda _: self.restart())
        self.root.bind("R", lambda _: self.restart())

        self.tick()

    def _set_key(self, key: str, state: bool) -> None:
        if key == "left":
            self.left_pressed = state
        elif key == "right":
            self.right_pressed = state
        elif key == "fire":
            self.fire_pressed = state

    def _make_invaders(self) -> None:
        self.invaders.clear()
        for row in range(self.invader_rows):
            for col in range(self.invader_cols):
                x = self.invader_start_x + col * (self.invader_w + self.invader_gap_x)
                y = self.invader_start_y + row * (self.invader_h + self.invader_gap_y)
                self.invaders.append(Invader(x=x, y=y))

    def _make_shields(self) -> None:
        self.shields.clear()
        shield_w = 110
        shield_h = 45
        y = HEIGHT - 140
        for i in range(4):
            x1 = 70 + i * 180
            self.shields.append((x1, y, x1 + shield_w, y + shield_h, 10))

    def restart(self) -> None:
        self.player_x = WIDTH / 2
        self.player_lives = 3
        self.score = 0
        self.level = 1
        self.invader_dx = 1.1
        self.enemy_fire_chance = 0.01
        self.bullets.clear()
        self._make_invaders()
        self._make_shields()
        self.running = True
        self.message = ""

    def tick(self) -> None:
        self.update()
        self.draw()
        self.root.after(FPS_MS, self.tick)

    def update(self) -> None:
        if not self.running:
            return

        if self.left_pressed and not self.right_pressed:
            self.player_x -= self.player_speed
        elif self.right_pressed and not self.left_pressed:
            self.player_x += self.player_speed
        self.player_x = max(self.player_w / 2, min(WIDTH - self.player_w / 2, self.player_x))

        if self.player_cooldown > 0:
            self.player_cooldown -= 1

        if self.fire_pressed and self.player_cooldown == 0:
            self.bullets.append(Bullet(self.player_x, self.player_y - self.player_h / 2 - 8, vy=-10, from_player=True))
            self.player_cooldown = 12

        move_down = False
        alive_invaders = [i for i in self.invaders if i.alive]
        if alive_invaders:
            leftmost = min(i.x for i in alive_invaders)
            rightmost = max(i.x for i in alive_invaders)
            if leftmost + self.invader_dx < 16 or rightmost + self.invader_w + self.invader_dx > WIDTH - 16:
                move_down = True
                self.invader_dx *= -1

            for inv in alive_invaders:
                inv.x += self.invader_dx
                if move_down:
                    inv.y += self.invader_step_down
                if random.random() < self.enemy_fire_chance:
                    self.bullets.append(Bullet(inv.x + self.invader_w / 2, inv.y + self.invader_h + 5, vy=5, from_player=False))
                if inv.y + self.invader_h >= self.player_y - self.player_h:
                    self.running = False
                    self.message = "GAME OVER - invaders reached you! Press R to restart"

        for b in self.bullets:
            b.y += b.vy
            if b.y < -20 or b.y > HEIGHT + 20:
                b.active = False

        for b in self.bullets:
            if not b.active:
                continue
            if b.from_player:
                for inv in self.invaders:
                    if inv.alive and self._in_rect(b.x, b.y, inv.x, inv.y, inv.x + self.invader_w, inv.y + self.invader_h):
                        inv.alive = False
                        b.active = False
                        self.score += 10
                        break
            else:
                if self._in_rect(
                    b.x,
                    b.y,
                    self.player_x - self.player_w / 2,
                    self.player_y - self.player_h / 2,
                    self.player_x + self.player_w / 2,
                    self.player_y + self.player_h / 2,
                ):
                    b.active = False
                    self.player_lives -= 1
                    if self.player_lives <= 0:
                        self.running = False
                        self.message = "GAME OVER - out of lives! Press R to restart"

        new_shields = []
        for x1, y1, x2, y2, hp in self.shields:
            hp_now = hp
            for b in self.bullets:
                if b.active and self._in_rect(b.x, b.y, x1, y1, x2, y2):
                    b.active = False
                    hp_now -= 1
            if hp_now > 0:
                new_shields.append((x1, y1, x2, y2, hp_now))
        self.shields = new_shields

        self.bullets = [b for b in self.bullets if b.active]

        if not any(i.alive for i in self.invaders):
            self.level += 1
            self.enemy_fire_chance = min(0.04, self.enemy_fire_chance + 0.004)
            self.invader_dx = (1.1 + 0.2 * self.level) * (1 if self.invader_dx > 0 else -1)
            self._make_invaders()

    def draw(self) -> None:
        self.canvas.delete("all")

        self.canvas.create_text(12, 12, anchor="nw", fill="#9ae6ff", font=("Menlo", 14),
                                text=f"Score: {self.score}   Lives: {self.player_lives}   Level: {self.level}")

        if self.running:
            self.canvas.create_rectangle(
                self.player_x - self.player_w / 2,
                self.player_y - self.player_h / 2,
                self.player_x + self.player_w / 2,
                self.player_y + self.player_h / 2,
                fill="#4ade80",
                outline="",
            )

        for inv in self.invaders:
            if not inv.alive:
                continue
            color = "#f43f5e" if int(inv.y / 10) % 2 == 0 else "#fb7185"
            self.canvas.create_rectangle(inv.x, inv.y, inv.x + self.invader_w, inv.y + self.invader_h, fill=color, outline="")
            self.canvas.create_rectangle(inv.x + 6, inv.y + 6, inv.x + 12, inv.y + 12, fill="#fff", outline="")
            self.canvas.create_rectangle(inv.x + 28, inv.y + 6, inv.x + 34, inv.y + 12, fill="#fff", outline="")

        for b in self.bullets:
            color = "#fde047" if b.from_player else "#93c5fd"
            self.canvas.create_rectangle(b.x - 2, b.y - 7, b.x + 2, b.y + 7, fill=color, outline="")

        for x1, y1, x2, y2, hp in self.shields:
            shade = max(40, min(180, hp * 16))
            color = f"#{shade:02x}{(shade + 30):02x}{shade:02x}"
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

        if not self.running:
            self.canvas.create_text(WIDTH / 2, HEIGHT / 2, fill="#fef08a", font=("Menlo", 18, "bold"), text=self.message)

        self.canvas.create_text(
            WIDTH / 2,
            HEIGHT - 14,
            fill="#94a3b8",
            font=("Menlo", 12),
            text="Controls: ←/→ move, Space shoot, R restart",
        )

    @staticmethod
    def _in_rect(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> bool:
        return x1 <= px <= x2 and y1 <= py <= y2


def main() -> None:
    root = tk.Tk()
    SpaceInvaders(root)
    root.mainloop()


if __name__ == "__main__":
    main()
