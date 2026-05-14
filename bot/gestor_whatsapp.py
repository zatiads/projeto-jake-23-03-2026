"""
gestor_whatsapp.py — Cliente HTTP do Jake OS para Jake WhatsApp.

Encapsula autenticação e chamadas aos endpoints de anúncios.
Nunca chama a Meta API diretamente — todo trabalho pesado fica no Jake OS.
"""
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

JAKE_OS_URL   = os.environ.get("JAKE_OS_URL", "http://localhost:5050")
JAKE_OS_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@jakeos.local")
JAKE_OS_SENHA = os.environ.get("ADMIN_PASSWORD", "Jake@2024!")


class GestorJakeOS:
    def __init__(self, base_url: str = JAKE_OS_URL, email: str = JAKE_OS_EMAIL, senha: str = JAKE_OS_SENHA):
        self._base    = base_url.rstrip("/")
        self._email   = email
        self._senha   = senha
        self._session = requests.Session()
        self._autenticado = False

    def login(self) -> bool:
        """Faz login no Jake OS e mantém cookie de sessão. Retorna True se OK."""
        try:
            resp = self._session.post(
                f"{self._base}/auth/login",
                data={"email": self._email, "password": self._senha},
                allow_redirects=True,
                timeout=10,
            )
            # Sucesso: redirect para "/" — falha: redirect para "/login?error=1"
            if "login" in resp.url and "error" in resp.url:
                logger.error("Jake OS: login falhou — credenciais incorretas")
                self._autenticado = False
                return False
            self._autenticado = True
            logger.info("Jake OS: login OK")
            return True
        except Exception as e:
            logger.error(f"Jake OS: erro no login: {e}")
            self._autenticado = False
            return False

    def _garantir_auth(self):
        if not self._autenticado:
            self.login()

    def subir_anuncio(self, cliente_ids: list, drive_url: str | None, orcamento: float,
                      campanha_nome: str, campanha_tipo: str = "MESSAGES",
                      arquivo_local: str | None = None,
                      arquivos_locais: list | None = None,
                      num_conjuntos: int = 1,
                      cri_por_conjunto: int | None = None,
                      orcamento_por_conjunto: float | None = None,
                      copy: dict | None = None,
                      copies_list: list | None = None) -> dict:
        """
        Prepara lote via Jake OS. Retorna dict com mc_token para consumir o stream.
        Lança RuntimeError em caso de falha.
        Aceita drive_url, arquivo_local (único) ou arquivos_locais (múltiplos).
        """
        self._garantir_auth()
        payload = {
            "cliente_ids":   cliente_ids,
            "orcamento":     orcamento,
            "campanha_nome": campanha_nome,
            "campanha_tipo": campanha_tipo,
        }
        if arquivos_locais:
            payload["arquivos_locais"] = arquivos_locais
        elif arquivo_local:
            payload["arquivo_local"] = arquivo_local
        else:
            payload["drive_url"] = drive_url or ""
        if num_conjuntos > 1:
            payload["num_conjuntos"] = num_conjuntos
        if cri_por_conjunto:
            payload["cri_por_conjunto"] = cri_por_conjunto
        if orcamento_por_conjunto:
            payload["orcamento_por_conjunto"] = orcamento_por_conjunto
        if copy:
            payload["copy"] = copy
        if copies_list:
            payload["copies_list"] = copies_list
        resp = self._session.post(
            f"{self._base}/api/anuncios/wa/subir",
            json=payload,
            timeout=60,
        )
        if resp.status_code == 401:
            # Sessão expirou — re-login e tenta uma vez mais
            self._autenticado = False
            self._garantir_auth()
            resp = self._session.post(
                f"{self._base}/api/anuncios/wa/subir",
                json=payload,
                timeout=60,
            )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro desconhecido no Jake OS"))
        return data  # {"mc_token": "...", "clientes": N, "tipo": "video/mp4"}

    def consumir_stream(self, mc_token: str) -> list:
        """
        Consome o SSE de /api/anuncios/multi-cliente/stream/<mc_token>.
        Retorna lista de eventos {tipo, cliente, status, ...}.
        """
        self._garantir_auth()
        eventos = []
        try:
            with self._session.get(
                f"{self._base}/api/anuncios/multi-cliente/stream/{mc_token}",
                stream=True,
                timeout=300,
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if line.startswith("data:"):
                        try:
                            ev = json.loads(line[5:].strip())
                            eventos.append(ev)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Erro ao consumir stream: {e}")
        return eventos

    def listar_campanhas(self, account_id: str, token_key: str) -> list:
        """Retorna lista de campanhas ativas/pausadas de uma conta."""
        self._garantir_auth()
        resp = self._session.get(
            f"{self._base}/api/anuncios/campanhas/{account_id}",
            params={"token_key": token_key},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro ao listar campanhas"))
        return data.get("campanhas", [])

    def listar_publicos_salvos(self, cliente_id: int) -> list:
        """Retorna lista de públicos salvos de um cliente via Jake OS."""
        self._garantir_auth()
        resp = self._session.get(
            f"{self._base}/api/anuncios/clientes/{cliente_id}/publicos-salvos",
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro ao listar públicos"))
        return data.get("publicos", [])

    def pausar_campanha(self, campaign_id: str, token_key: str) -> bool:
        """Pausa uma campanha. Retorna True se OK."""
        return self._set_status(campaign_id, "PAUSED", token_key)

    def ativar_campanha(self, campaign_id: str, token_key: str) -> bool:
        """Ativa uma campanha. Retorna True se OK."""
        return self._set_status(campaign_id, "ACTIVE", token_key)

    def _set_status(self, campaign_id: str, status: str, token_key: str) -> bool:
        self._garantir_auth()
        resp = self._session.patch(
            f"{self._base}/api/anuncios/campanha/{campaign_id}/status",
            json={"status": status, "token_key": token_key},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", "Erro ao atualizar status"))
        return data.get("ok", False)


# Instância singleton — reutilizar sessão entre chamadas
_gestor = None

def get_gestor() -> GestorJakeOS:
    global _gestor
    if _gestor is None:
        _gestor = GestorJakeOS()
        _gestor.login()
    return _gestor
