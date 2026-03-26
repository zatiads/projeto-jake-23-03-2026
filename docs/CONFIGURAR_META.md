# Configurar Meta (Facebook) para o Jake IA

Para o bot **puxar relatórios** direto da Meta (ex: "relatório Carazinho últimos 7 dias"), configure as variáveis abaixo.

## 1. Token de acesso (obrigatório)

- Acesse [Meta for Developers](https://developers.facebook.com/) → seu App → **Ferramentas** → **Graph API Explorer**.
- Selecione o App e as permissões: `ads_read`, `ads_management`, `business_management`.
- Gere um **User Token** e troque por um **Long-Lived Token** (ferramentas do Meta ou API).
- Exporte no servidor:
  ```bash
  export META_ACCESS_TOKEN="seu_token_aqui"
  ```

## 2. Conta de anúncios

- No [Gerenciador de Anúncios](https://business.facebook.com/) pegue o ID da conta (ex: `123456789012345`).
- A API usa o formato `act_123456789012345`.

**Opção A – Uma conta (padrão):**
```bash
export META_AD_ACCOUNT_ID="act_123456789012345"
```

**Opção B – Por cliente (relatório Carazinho, etc.):**
```bash
export META_AD_ACCOUNT_ID="act_123456789012345"
export META_AD_ACCOUNT_CARAZINHO="act_123456789012345"
```

Ou edite `/root/config_meta.py` e preencha `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` e o dicionário `CLIENTE_CONTAS` (ex: `"carazinho": "act_..."`).

## 3. Rodar o bot com Meta

```bash
cd /root && source venv/bin/activate
export META_ACCESS_TOKEN="..."
export META_AD_ACCOUNT_ID="act_..."
python3 jake_telegram.py
```

No Telegram:

- **/relatorio carazinho 7** — relatório dos últimos 7 dias.
- Ou escreva: "relatório Carazinho últimos 7 dias".

## 4. Criar campanha pelo Telegram

A funcionalidade **/criar_campanha** está preparada no código e será ativada em seguida (subir campanha via Telegram antes do frontend).
