"""
Processo fixo de voz (roda no venv do /opt/edge-tts).
Lê um JSON por linha no stdin {"texto", "voz", "ritmo"} e devolve uma linha com o mp3 em base64
(vazia se falhar). Evita abrir o edge-tts do zero a cada fala (~1 s a menos).
"""
import asyncio
import base64
import json
import sys

import edge_tts


async def gerar(texto, voz, ritmo):
    audio = b""
    async for parte in edge_tts.Communicate(texto, voz, rate=ritmo).stream():
        if parte["type"] == "audio":
            audio += parte["data"]
    return audio


def main():
    loop = asyncio.new_event_loop()
    for linha in sys.stdin:
        try:
            pedido = json.loads(linha)
            audio = loop.run_until_complete(asyncio.wait_for(
                gerar(pedido["texto"], pedido["voz"], pedido["ritmo"]), timeout=10))
            saida = base64.b64encode(audio).decode()
        except Exception as e:
            print(f"tts_worker: {e}", file=sys.stderr, flush=True)
            saida = ""
        sys.stdout.write(saida + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
