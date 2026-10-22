"""
Mais 3 sons de iniciação no clima "Homem de Ferro": servos e metal (armadura), bipes de HUD (JARVIS)
e o reator arc carregando. Usa as mesmas peças do som_abertura.py. Saída em visual/som/.
"""
import numpy as np

from som_abertura import SR, colocar, env, filtro, nota, reverb, rng, t, SAIDA
import subprocess
import wave


def suave(x, ms=6):
    """Fade curtinho nas pontas pra nenhum evento estalar."""
    n = min(int(ms / 1000 * SR), len(x) // 2)
    if n:
        x[:n] *= np.linspace(0, 1, n)
        x[-n:] *= np.linspace(1, 0, n)
    return x


def tom(freq, dur, forma="sin"):
    x = t(dur)
    if forma == "quadrada":
        s = np.sign(np.sin(2 * np.pi * freq * x)) * 0.5
        s = filtro(s, 6000)
    else:
        s = np.sin(2 * np.pi * freq * x)
    return suave(s)


def varredura(f0, f1, dur, vibrato=0.0):
    x = t(dur)
    f = np.geomspace(f0, f1, len(x)) * (1 + vibrato * np.sin(2 * np.pi * 18 * x))
    return suave(np.sin(2 * np.pi * np.cumsum(f) / SR), 20)


def servo(dur, f0, f1):
    """Motor elétrico: dente-de-serra filtrado com pitch subindo e roncando."""
    x = t(dur)
    f = np.linspace(f0, f1, len(x))
    fase = np.cumsum(f) / SR
    serra = 2 * (fase % 1) - 1
    s = filtro(serra, 1800) + 0.3 * filtro(rng.standard_normal(len(x)), 900)
    return suave(s * env(len(x), 0.05, 0, r=0.12), 15)


def metal(freq, dur=0.9):
    """Batida metálica: clique + parciais inarmônicas (tipo placa da armadura encaixando)."""
    x = t(dur)
    parciais = [1, 2.76, 5.4, 8.93]
    s = sum(np.sin(2 * np.pi * freq * p * x) * np.exp(-x * (6 + 4 * i)) / (i + 1) for i, p in enumerate(parciais))
    clique = filtro(rng.standard_normal(len(x)), 3000, "high") * np.exp(-x * 80)
    return suave(s * 0.8 + clique * 0.5)


def salvar(nome, mix, fade_inicio):
    final = reverb(mix, cauda=2.0, mix=0.28)
    final = np.tanh(final * 1.3)
    final /= np.max(np.abs(final)) * 1.12
    wav = SAIDA / f"{nome}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((final * 32767).astype(np.int16).tobytes())
    mp3 = SAIDA / f"{nome}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", f"afade=t=out:st={fade_inicio}:d=1.2",
                    "-b:a", "160k", str(mp3)], check=True)
    wav.unlink()
    print(mp3.name, round(len(final) / SR, 1), "s")


def armadura():
    """D: servos girando, placas encaixando (3 batidas metálicas), motor sobe e o sistema estabiliza num acorde."""
    mix = np.zeros(int(5.4 * SR))
    colocar(mix, servo(0.7, 70, 160), 0.0, 0.35)
    colocar(mix, metal(220), 0.55, 0.5)
    colocar(mix, servo(0.5, 110, 240), 0.75, 0.3)
    colocar(mix, metal(262), 1.15, 0.5)
    colocar(mix, servo(0.45, 150, 330), 1.3, 0.3)
    colocar(mix, metal(330), 1.65, 0.55)
    colocar(mix, varredura(180, 1400, 0.9) * env(int(0.9 * SR), 0.6, 0), 1.7, 0.18)
    # estabiliza: grave + acorde maior aberto
    x = t(2.4)
    colocar(mix, np.sin(2 * np.pi * 55 * x) * np.exp(-x * 1.6), 2.55, 0.7)
    for i, st in enumerate([0, 7, 12, 16, 19]):
        som = nota(110 * 2 ** (st / 12), 2.0, detune=0.004, brilho=4) * env(int(2.0 * SR), 0.03, 0.5, 0.5, r=1.4)
        colocar(mix, filtro(som, 4800), 2.55 + i * 0.01, 0.13)
    salvar("abertura_D_armadura", mix, 5.4)


def jarvis():
    """E: HUD inicializando — chuva de bipes digitais, varredura de scanner, e o 'pronto' em dois tons."""
    mix = np.zeros(int(5.0 * SR))
    escala = [880, 988, 1175, 1319, 1568, 1760, 2093]
    for k in range(26):  # bipes de dados acelerando
        quando = 0.05 + 1.4 * (k / 26) ** 0.8
        f = escala[rng.integers(len(escala))] * (2 if rng.random() < 0.25 else 1)
        colocar(mix, tom(f, 0.045, "quadrada") * 0.6, quando, 0.12)
    colocar(mix, varredura(400, 3200, 0.8, vibrato=0.01) * env(int(0.8 * SR), 0.7, 0), 0.9, 0.14)  # scanner
    ruido = filtro(rng.standard_normal(int(1.3 * SR)), 5000, "high") * env(int(1.3 * SR), 1.0, 0, r=0.25)
    colocar(mix, suave(ruido, 30), 0.4, 0.02)
    # "sistema pronto": dois tons limpos + grave suave
    colocar(mix, tom(1318.5, 0.16) * env(int(0.16 * SR), 0.005, 0.1, 0.4), 1.75, 0.35)
    colocar(mix, tom(1975.5, 0.5) * env(int(0.5 * SR), 0.005, 0.2, 0.3, r=0.3), 1.93, 0.35)
    x = t(2.0)
    colocar(mix, np.sin(2 * np.pi * 82.4 * x) * env(len(x), 0.02, 0.4, 0.4, r=1.4), 1.75, 0.5)
    for i, st in enumerate([0, 7, 12, 19]):
        som = nota(164.8 * 2 ** (st / 12), 1.8, detune=0.003, brilho=3) * env(int(1.8 * SR), 0.15, 0.4, 0.5, r=1.2)
        colocar(mix, filtro(som, 5000), 1.95, 0.08)
    salvar("abertura_E_jarvis", mix, 5.0)


def reator():
    """F: reator arc carregando — zumbido agudo subindo com tremor elétrico, faíscas, e o 'thump' com hum estável."""
    mix = np.zeros(int(5.6 * SR))
    carga = varredura(220, 2600, 1.9, vibrato=0.006) * env(int(1.9 * SR), 1.7, 0)
    trem = 1 + 0.35 * np.sin(2 * np.pi * np.geomspace(6, 40, len(carga)) * t(1.9))
    colocar(mix, carga * trem, 0.0, 0.22)
    colocar(mix, varredura(110, 1300, 1.9) * env(int(1.9 * SR), 1.7, 0), 0.0, 0.12)  # oitava de baixo
    for k in range(14):  # faíscas elétricas
        n = int(rng.uniform(0.008, 0.03) * SR)
        colocar(mix, suave(filtro(rng.standard_normal(n), 2500, "high"), 2), 0.6 + k * 0.09 + rng.uniform(0, 0.05),
                0.12 + 0.1 * k / 14)
    # descarga: thump + clique
    x = t(1.4)
    colocar(mix, np.sin(2 * np.pi * 48 * x * (1 + 0.8 * np.exp(-x * 14))) * np.exp(-x * 2.6), 1.95, 0.95)
    colocar(mix, suave(filtro(rng.standard_normal(int(0.04 * SR)), 2000, "high")), 1.95, 0.3)
    # hum estável do reator + brilho
    x = t(2.6)
    hum = (np.sin(2 * np.pi * 110 * x) + 0.5 * np.sin(2 * np.pi * 220.6 * x) + 0.25 * np.sin(2 * np.pi * 330 * x))
    colocar(mix, hum * env(len(x), 0.08, 0.6, 0.45, r=1.6), 2.0, 0.22)
    for i, st in enumerate([0, 7, 12, 14, 19]):
        som = nota(220 * 2 ** (st / 12), 2.3, detune=0.005, brilho=3) * env(int(2.3 * SR), 0.05, 0.5, 0.45, r=1.6)
        colocar(mix, filtro(som, 5500), 2.0 + i * 0.015, 0.09)
    salvar("abertura_F_reator", mix, 5.6)


if __name__ == "__main__":
    armadura()
    jarvis()
    reator()
