"""
Sintetiza o som de "sistema iniciando" do Jake (sem samples, sem IA): grave subindo, varredura de ar,
impacto e acorde brilhante com cauda. Gera 3 variações em visual/som/.
"""
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
SAIDA = Path(__file__).resolve().parent / "som"
rng = np.random.default_rng(7)


def t(seg):
    return np.arange(int(seg * SR)) / SR


def env(n, a, d, sus=1.0, r=None):
    """Envelope em amostras: ataque, (decaimento até sus) e liberação no fim."""
    e = np.ones(n) * sus
    ia, idd = int(a * SR), int(d * SR)
    e[:ia] = np.linspace(0, 1, ia) ** 2 if ia else e[:ia]
    if idd:
        e[ia:ia + idd] = np.linspace(1, sus, min(idd, n - ia))
    if r:
        ir = int(r * SR)
        e[-ir:] *= np.linspace(1, 0, ir) ** 1.5
    return e


def nota(freq, dur, detune=0.0, brilho=3):
    x = t(dur)
    s = sum(np.sin(2 * np.pi * freq * k * (1 + detune) * x) / k ** 1.6 for k in range(1, brilho + 1))
    s += sum(np.sin(2 * np.pi * freq * k * (1 - detune) * x) / k ** 1.6 for k in range(1, brilho + 1))
    return s / 2


def filtro(x, corte, tipo="low", ordem=4):
    sos = butter(ordem, corte, btype=tipo, fs=SR, output="sos")
    return sosfilt(sos, x)


def reverb(x, cauda=2.2, mix=0.35):
    n = int(cauda * SR)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = filtro(ir, 6000)
    molhado = np.convolve(x, ir)[: len(x) + n]
    molhado = np.pad(molhado, (0, len(x) + n - len(molhado)))
    seco = np.pad(x, (0, n))
    molhado /= np.max(np.abs(molhado)) + 1e-9
    return seco * (1 - mix) + molhado * mix * np.max(np.abs(x))


def colocar(base, som, inicio, ganho=1.0):
    i = int(inicio * SR)
    fim = min(len(base), i + len(som))
    base[i:fim] += som[: fim - i] * ganho


def gerar(nome, tonica, acorde, dur=4.6, impacto=1.55, arpejo=True, sweep_fim=7000):
    mix = np.zeros(int(dur * SR))

    # 1) grave subindo (respiração do sistema)
    x = t(impacto + 0.2)
    f = np.linspace(tonica / 4, tonica / 2, len(x))
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(x), impacto * 0.9, 0)
    colocar(mix, sub, 0, 0.55)

    # 2) varredura de ar (ruído filtrado que abre)
    x = t(impacto)
    ruido = rng.standard_normal(len(x))
    # abre o filtro sem emenda: mistura versões do mesmo ruído com cortes crescentes (crossfade suave)
    cortes = np.geomspace(300, sweep_fim, 8)
    camadas = [filtro(ruido, c) for c in cortes]
    pos = np.linspace(0, len(cortes) - 1, len(x))
    ar = np.zeros(len(x))
    for k, cam in enumerate(camadas):
        ar += cam * np.clip(1 - np.abs(pos - k), 0, 1)
    ar *= env(len(ar), impacto * 0.95, 0) * 0.5
    colocar(mix, ar, 0.05, 0.22)

    # 3) impacto: grave seco + clique
    x = t(1.2)
    boom = np.sin(2 * np.pi * (tonica / 2) * x * (1 + 0.6 * np.exp(-x * 12))) * np.exp(-x * 3.2)
    clique = filtro(rng.standard_normal(int(0.03 * SR)), 2500, "high") * np.linspace(1, 0, int(0.03 * SR))
    colocar(mix, boom, impacto, 0.9)
    colocar(mix, clique, impacto, 0.25)

    # 4) acorde brilhante (pad levemente desafinado) com cauda
    for i, semitom in enumerate(acorde):
        fq = tonica * 2 ** (semitom / 12)
        dur_n = dur - impacto
        som = nota(fq, dur_n, detune=0.004 + i * 0.0007, brilho=4)
        som *= env(len(som), 0.04 + i * 0.015, 0.6, 0.55, r=dur_n * 0.7)
        colocar(mix, filtro(som, 5200), impacto + i * 0.012, 0.16)

    # 5) brilhos: arpejo rápido subindo logo depois do impacto
    if arpejo:
        for k, semitom in enumerate([12, 19, 24, 28, 31, 36]):
            fq = tonica * 2 ** (semitom / 12)
            som = nota(fq, 0.9, detune=0.002, brilho=2) * env(int(0.9 * SR), 0.005, 0.25, 0.0)
            colocar(mix, som, impacto + 0.08 + k * 0.07, 0.07)

    final = reverb(mix, cauda=2.4, mix=0.32)
    final = np.tanh(final * 1.4)  # cola tudo e segura o pico
    final /= np.max(np.abs(final)) * 1.12
    wav = SAIDA / f"{nome}.wav"
    pcm = (final * 32767).astype(np.int16)
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    mp3 = SAIDA / f"{nome}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", "afade=t=out:st=5.4:d=1.2",
                    "-b:a", "160k", str(mp3)], check=True)
    wav.unlink()
    print(mp3.name, round(len(final) / SR, 1), "s")


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    # A: cinematográfico (mi maior com 9ª) — clássico de "carro premium ligando"
    gerar("abertura_A_cinematico", 164.81, [0, 7, 12, 16, 19, 26])
    # B: frio e tecnológico (lá menor com 9ª, sem arpejo) — mais sério, tipo nave
    gerar("abertura_B_nave", 110.0, [0, 7, 12, 15, 19, 26], arpejo=False, sweep_fim=4500)
    # C: curto e brilhante (ré maior 7M) — mais "assistente", rápido
    gerar("abertura_C_assistente", 146.83, [0, 7, 11, 16, 19], dur=3.4, impacto=0.9)
