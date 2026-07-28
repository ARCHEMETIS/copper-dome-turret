"""Generate presentation figures for the Copper Dome Turret slides."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "slide-assets"

NAVY = "#17324D"
BLUE = "#2F6B9A"
TEAL = "#2A9D8F"
ORANGE = "#F4A261"
RED = "#E76F51"
PURPLE = "#7B61A8"
GREEN = "#4C956C"
GRAY = "#5F6B73"
LIGHT_BLUE = "#E7F2FA"
LIGHT_TEAL = "#E6F5F2"
LIGHT_ORANGE = "#FFF0DF"
LIGHT_PURPLE = "#F0EAF8"


def add_box(
    ax,
    center,
    width,
    height,
    label,
    *,
    facecolor=LIGHT_BLUE,
    edgecolor=NAVY,
    fontsize=10,
    linewidth=1.8,
):
    """Add a rounded labelled box and return its bounds."""
    x, y = center
    left = x - width / 2
    bottom = y - height / 2
    patch = FancyBboxPatch(
        (left, bottom),
        width,
        height,
        boxstyle="round,pad=0.04,rounding_size=0.10",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=3,
    )
    ax.add_patch(patch)
    ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=NAVY,
        fontweight="bold",
        zorder=4,
    )
    return left, bottom, left + width, bottom + height


def add_arrow(ax, start, end, *, color=GRAY, linewidth=2.0, mutation_scale=15):
    """Add a straight arrow."""
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation_scale,
        linewidth=linewidth,
        color=color,
        shrinkA=0,
        shrinkB=0,
        zorder=2,
    )
    ax.add_patch(arrow)


def add_elbow_arrow(
    ax,
    points,
    *,
    color=GRAY,
    linewidth=2.0,
    linestyle="-",
    mutation_scale=14,
):
    """Add a polyline whose final segment ends in an arrow."""
    for start, end in zip(points[:-2], points[1:-1]):
        ax.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            solid_capstyle="round",
            zorder=1,
        )
    add_arrow(
        ax,
        points[-2],
        points[-1],
        color=color,
        linewidth=linewidth,
        mutation_scale=mutation_scale,
    )


def make_block_diagram():
    """Create the horizontal software-to-hardware data-flow diagram."""
    fig, ax = plt.subplots(figsize=(18, 5.5))
    ax.set_xlim(0, 18.2)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    nodes = [
        ((1.35, 3.15), 2.2, 1.15, "Phone camera\n(Camo)", LIGHT_BLUE),
        ((4.1, 3.15), 2.35, 1.15, "PC: YOLOv8s\ndetect", LIGHT_TEAL),
        ((6.95, 3.15), 2.35, 1.15, "PC: aim\ncontroller", LIGHT_TEAL),
        ((9.65, 3.15), 2.25, 1.15, "pyFirmata2\n/ USB", LIGHT_PURPLE),
        (
            (12.75, 3.15),
            3.0,
            1.45,
            "Arduino Uno\n(StandardFirmata,\nI/O only)",
            LIGHT_ORANGE,
        ),
    ]

    bounds = []
    for center, width, height, label, color in nodes:
        bounds.append(
            add_box(
                ax,
                center,
                width,
                height,
                label,
                facecolor=color,
                fontsize=10.5,
            )
        )

    for left_box, right_box in zip(bounds[:-1], bounds[1:]):
        add_arrow(
            ax,
            (left_box[2] + 0.10, 3.15),
            (right_box[0] - 0.10, 3.15),
            color=BLUE,
            linewidth=2.2,
        )

    upper = add_box(
        ax,
        (16.45, 4.15),
        3.15,
        1.15,
        "L298N -> flywheel\nmotors x2",
        facecolor=LIGHT_ORANGE,
        fontsize=10.5,
    )
    lower = add_box(
        ax,
        (16.45, 2.15),
        3.15,
        1.15,
        "pan / tilt\nservos",
        facecolor=LIGHT_BLUE,
        fontsize=10.5,
    )

    arduino_right = bounds[-1][2]
    split_x = 14.75
    ax.plot(
        [arduino_right, split_x],
        [3.15, 3.15],
        color=BLUE,
        linewidth=2.2,
        zorder=1,
    )
    ax.scatter([split_x], [3.15], s=34, color=BLUE, zorder=3)
    add_elbow_arrow(
        ax,
        [(split_x, 3.15), (split_x, 4.15), (upper[0] - 0.10, 4.15)],
        color=BLUE,
        linewidth=2.2,
    )
    add_elbow_arrow(
        ax,
        [(split_x, 3.15), (split_x, 2.15), (lower[0] - 0.10, 2.15)],
        color=BLUE,
        linewidth=2.2,
    )

    ax.text(
        9.1,
        0.55,
        "All logic runs in Python on the PC -- the Arduino holds no logic",
        ha="center",
        va="center",
        fontsize=12,
        color=NAVY,
        fontweight="bold",
    )

    fig.savefig(
        OUTPUT_DIR / "fig-block-diagram.png",
        dpi=300,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.12,
    )
    plt.close(fig)


def make_circuit_diagram():
    """Create the conceptual power, control, and grounding diagram."""
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    battery = add_box(
        ax,
        (1.55, 7.85),
        2.5,
        1.0,
        "2x 18650\n(7.4V)",
        facecolor=LIGHT_ORANGE,
        fontsize=11,
    )
    l298n = add_box(
        ax,
        (5.8, 7.85),
        2.0,
        1.0,
        "L298N",
        facecolor=LIGHT_ORANGE,
        fontsize=11,
    )
    motors = add_box(
        ax,
        (10.0, 7.85),
        3.0,
        1.0,
        "DC motor x2\n(flywheel)",
        facecolor=LIGHT_ORANGE,
        fontsize=11,
    )
    buck = add_box(
        ax,
        (5.45, 5.55),
        2.7,
        1.0,
        "Buck converter\n(6V)",
        facecolor=LIGHT_TEAL,
        fontsize=10.5,
    )
    servo_rail = add_box(
        ax,
        (9.2, 5.55),
        3.4,
        1.2,
        "Servo rail\n(Sensor Shield jumper removed)",
        facecolor=LIGHT_TEAL,
        fontsize=10,
    )
    pan = add_box(
        ax,
        (14.25, 6.55),
        2.5,
        0.9,
        "pan servo D9",
        facecolor=LIGHT_BLUE,
        fontsize=10.5,
    )
    tilt = add_box(
        ax,
        (14.25, 4.55),
        2.5,
        0.9,
        "tilt servo D10",
        facecolor=LIGHT_BLUE,
        fontsize=10.5,
    )
    pc = add_box(
        ax,
        (1.55, 2.7),
        2.5,
        1.0,
        "PC",
        facecolor=LIGHT_PURPLE,
        fontsize=11,
    )
    arduino = add_box(
        ax,
        (5.5, 2.7),
        2.8,
        1.0,
        "Arduino Uno",
        facecolor=LIGHT_PURPLE,
        fontsize=11,
    )

    add_arrow(
        ax,
        (battery[2], 7.85),
        (l298n[0], 7.85),
        color=ORANGE,
        linewidth=2.6,
    )
    ax.text(3.75, 8.08, "7.4V", ha="center", va="bottom", color=RED, fontsize=9.5)
    add_arrow(
        ax,
        (l298n[2], 7.85),
        (motors[0], 7.85),
        color=ORANGE,
        linewidth=2.6,
    )
    ax.text(
        7.9,
        8.08,
        "motor power",
        ha="center",
        va="bottom",
        color=RED,
        fontsize=9.5,
    )
    add_elbow_arrow(
        ax,
        [(battery[2], 7.58), (3.35, 7.58), (3.35, 5.55), (buck[0], 5.55)],
        color=ORANGE,
        linewidth=2.6,
    )
    ax.text(3.52, 6.55, "7.4V", ha="left", va="center", color=RED, fontsize=9.5)
    add_arrow(
        ax,
        (buck[2], 5.55),
        (servo_rail[0], 5.55),
        color=TEAL,
        linewidth=2.6,
    )
    ax.text(
        7.3,
        5.82,
        "6V servo power",
        ha="center",
        va="bottom",
        color=GREEN,
        fontsize=9.5,
    )

    power_split_x = 12.2
    ax.plot(
        [servo_rail[2], power_split_x],
        [5.55, 5.55],
        color=TEAL,
        linewidth=2.6,
        zorder=1,
    )
    ax.scatter([power_split_x], [5.55], s=30, color=TEAL, zorder=3)
    add_elbow_arrow(
        ax,
        [(power_split_x, 5.55), (power_split_x, 6.55), (pan[0], 6.55)],
        color=TEAL,
        linewidth=2.6,
    )
    add_elbow_arrow(
        ax,
        [(power_split_x, 5.55), (power_split_x, 4.55), (tilt[0], 4.55)],
        color=TEAL,
        linewidth=2.6,
    )

    add_arrow(
        ax,
        (pc[2], 2.7),
        (arduino[0], 2.7),
        color=BLUE,
        linewidth=2.4,
    )
    ax.text(3.53, 2.97, "USB", ha="center", va="bottom", color=BLUE, fontsize=10)

    add_elbow_arrow(
        ax,
        [
            (5.55, arduino[3]),
            (7.35, 3.2),
            (7.35, 7.15),
            (6.4, 7.15),
            (6.4, l298n[1]),
        ],
        color=PURPLE,
        linewidth=2.1,
    )
    ax.text(
        7.55,
        4.15,
        "PWM: ENA D5, ENB D6\n"
        "Direction: IN1 D2, IN2 D4\n"
        "IN3 D7, IN4 D8",
        ha="left",
        va="center",
        color=PURPLE,
        fontsize=9.5,
        linespacing=1.3,
    )

    add_elbow_arrow(
        ax,
        [
            (arduino[2], 2.9),
            (12.55, 2.9),
            (12.55, 6.55),
            (pan[0], 6.55),
        ],
        color=BLUE,
        linewidth=1.9,
    )
    add_elbow_arrow(
        ax,
        [
            (arduino[2], 2.5),
            (12.75, 2.5),
            (12.75, 4.55),
            (tilt[0], 4.55),
        ],
        color=BLUE,
        linewidth=1.9,
    )
    ax.text(
        9.65,
        3.13,
        "servo signal D9",
        ha="center",
        va="bottom",
        color=BLUE,
        fontsize=9.5,
    )
    ax.text(
        9.65,
        2.28,
        "servo signal D10",
        ha="center",
        va="top",
        color=BLUE,
        fontsize=9.5,
    )

    ground_y = 0.85
    ax.plot(
        [0.35, 12.2],
        [ground_y, ground_y],
        color=GRAY,
        linewidth=2.4,
        linestyle="--",
        zorder=1,
    )
    ax.text(
        6.3,
        0.42,
        "common GND",
        ha="center",
        va="center",
        color=GRAY,
        fontsize=11,
        fontweight="bold",
    )
    ground_paths = [
        [(battery[0], 7.75), (0.18, 7.75), (0.18, ground_y), (0.35, ground_y)],
        [(l298n[2], 7.6), (7.15, 7.6), (7.15, ground_y)],
        [(buck[0], 5.3), (3.7, 5.3), (3.7, ground_y)],
        [(5.5, arduino[1]), (5.5, ground_y)],
        [(9.2, servo_rail[1]), (9.2, ground_y)],
    ]
    for path in ground_paths:
        xs, ys = zip(*path)
        ax.plot(
            xs,
            ys,
            color=GRAY,
            linewidth=1.8,
            linestyle="--",
            zorder=1,
        )
        ax.scatter([path[-1][0]], [path[-1][1]], s=24, color=GRAY, zorder=3)

    ax.text(
        8.0,
        8.75,
        "Power, control, and grounding overview",
        ha="center",
        va="center",
        fontsize=14,
        color=NAVY,
        fontweight="bold",
    )

    fig.savefig(
        OUTPUT_DIR / "fig-circuit.png",
        dpi=300,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.12,
    )
    plt.close(fig)


def make_fp_rate_chart():
    """Create the grouped false-positive-rate chart."""
    thresholds = ["0.20", "0.30", "0.50"]
    train_4 = np.array([8.0, 5.7, 4.5])
    train_5 = np.array([1.1, 1.1, 0.0])
    x = np.arange(len(thresholds))
    width = 0.34

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_4 = ax.bar(
        x - width / 2,
        train_4,
        width,
        label="train-4",
        color=BLUE,
        edgecolor=NAVY,
        linewidth=0.8,
    )
    bars_5 = ax.bar(
        x + width / 2,
        train_5,
        width,
        label="train-5",
        color=ORANGE,
        edgecolor=RED,
        linewidth=0.8,
    )

    ax.set_title(
        "False positives on 88 unseen-room background images",
        fontsize=14,
        fontweight="bold",
        color=NAVY,
        pad=14,
    )
    ax.set_xlabel("Confidence threshold", fontsize=11)
    ax.set_ylabel("FP rate (%)", fontsize=11)
    ax.set_xticks(x, thresholds)
    ax.set_ylim(0, 9.3)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bars in (bars_4, bars_5):
        for bar in bars:
            value = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.16,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=NAVY,
            )

    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "fig-fp-rate.png",
        dpi=300,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.12,
    )
    plt.close(fig)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    make_block_diagram()
    make_circuit_diagram()
    make_fp_rate_chart()


if __name__ == "__main__":
    main()
