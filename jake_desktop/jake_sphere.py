#!/usr/bin/env python3
"""
Jake Desktop - Interface visual estilo Jarvis
Esfera de energia holográfica flutuante (base visual).
"""

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import QPainter, QRadialGradient, QColor, QPen, QBrush, QLinearGradient


class EnergySphere(QWidget):
    """Widget que desenha a esfera de energia holográfica com efeito pulsante."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pulse_phase = 0.0  # 0..1 para animação
        self._glow_phase = 0.0
        self.setFixedSize(140, 140)
        self._start_pulse_animation()

    def _start_pulse_animation(self):
        """Inicia o timer para o efeito de pulsação."""
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(50)  # ~20 FPS para animação suave

    def _update_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.03) % 1.0
        self._glow_phase = (self._glow_phase + 0.02) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        cx, cy = self.width() // 2, self.height() // 2
        base_radius = 48

        # Intensidade do pulso: varia entre 0.85 e 1.15
        import math
        pulse = 0.9 + 0.2 * math.sin(self._pulse_phase * 2 * math.pi)
        glow_intensity = 0.6 + 0.4 * math.sin(self._glow_phase * 2 * math.pi)

        # ---- 1. Aura externa (brilho suave) ----
        outer_radius = int(base_radius * 1.8 * pulse)
        gradient_outer = QRadialGradient(cx, cy, outer_radius, cx, cy)
        gradient_outer.setColorAt(0.0, QColor(0, 255, 255, int(40 * glow_intensity)))
        gradient_outer.setColorAt(0.5, QColor(0, 200, 255, int(20 * glow_intensity)))
        gradient_outer.setColorAt(1.0, QColor(0, 255, 255, 0))
        painter.setBrush(QBrush(gradient_outer))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(cx, cy), outer_radius, outer_radius)

        # ---- 2. Anel médio (cyan elétrico) ----
        mid_radius = int(base_radius * 1.25 * pulse)
        gradient_mid = QRadialGradient(cx, cy, mid_radius, cx, cy)
        gradient_mid.setColorAt(0.0, QColor(255, 255, 255, int(180 * glow_intensity)))
        gradient_mid.setColorAt(0.3, QColor(100, 255, 255, int(120 * glow_intensity)))
        gradient_mid.setColorAt(0.6, QColor(0, 220, 255, 80))
        gradient_mid.setColorAt(1.0, QColor(0, 180, 220, 0))
        painter.setBrush(QBrush(gradient_mid))
        painter.drawEllipse(QPoint(cx, cy), mid_radius, mid_radius)

        # ---- 3. Núcleo (branco / cyan intenso) ----
        core_radius = int(base_radius * 0.65 * pulse)
        gradient_core = QRadialGradient(cx, cy, core_radius, cx, cy)
        gradient_core.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient_core.setColorAt(0.4, QColor(200, 255, 255, 220))
        gradient_core.setColorAt(0.7, QColor(0, 255, 255, 150))
        gradient_core.setColorAt(1.0, QColor(0, 200, 255, 60))
        painter.setBrush(QBrush(gradient_core))
        painter.drawEllipse(QPoint(cx, cy), core_radius, core_radius)

        # ---- 4. Centro branco brilhante (ponto de luz) ----
        inner_radius = int(base_radius * 0.25 * pulse)
        gradient_inner = QRadialGradient(cx, cy, inner_radius, cx, cy)
        gradient_inner.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient_inner.setColorAt(0.6, QColor(220, 255, 255, 200))
        gradient_inner.setColorAt(1.0, QColor(150, 255, 255, 0))
        painter.setBrush(QBrush(gradient_inner))
        painter.drawEllipse(QPoint(cx, cy), inner_radius, inner_radius)

        painter.end()


class JakeSphereWindow(QMainWindow):
    """Janela frameless e transparente que exibe apenas a esfera de energia."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jake")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.sphere = EnergySphere(self)
        self.setCentralWidget(self.sphere)

        # Tamanho da janela = tamanho do widget da esfera
        self.setFixedSize(self.sphere.size())
        self._center_on_screen()

    def _center_on_screen(self):
        """Centraliza a janela na tela principal."""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Jake Desktop")
    window = JakeSphereWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
