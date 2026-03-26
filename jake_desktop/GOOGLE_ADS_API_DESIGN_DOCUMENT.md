# Technical Design Document — Google Ads API Integration
**Application:** Jake OS — Internal Agency Reporting Platform
**Version:** 1.0
**Date:** March 2026

---

## 1. Application Overview

Jake OS is a private, internal web application built for a digital marketing agency to centralize campaign performance reporting. The platform is hosted on a private server and is accessible only to authenticated agency staff through a session-based login system.

The application currently integrates with the **Meta Ads API** to retrieve campaign metrics for multiple client accounts and automatically generates weekly performance reports. The purpose of this Google Ads API integration is to extend the same reporting capability to Google Ads campaigns managed by the agency.

**The tool is strictly internal. It is not a SaaS product, is not distributed to third parties, and does not expose client data externally.**

---

## 2. How the Application Connects to the Google Ads API

### 2.1 Architecture

```
[Agency Staff Browser]
        │
        │ HTTPS (authenticated session)
        ▼
[Jake OS — Flask Web Server]
        │
        │ Server-side request (Python)
        ▼
[Google Ads API]
        │
        │ JSON response (metrics)
        ▼
[Jake OS — Report Generator]
        │
        │ Formatted weekly report text
        ▼
[Agency Staff — copies report to WhatsApp/Slack]
```

### 2.2 Authentication Flow

1. Agency staff logs into Jake OS with email/password credentials.
2. Jake OS backend holds the Google Ads OAuth2 refresh token and developer token as server-side environment variables (never exposed to the browser).
3. On each API request, the backend exchanges the refresh token for a short-lived access token using the Google Ads Python client library.
4. The access token is used server-side to query the Google Ads API. It is never returned to the frontend.

---

## 3. Data Flow

### 3.1 What Data Is Requested

Jake OS queries the following read-only metrics from the Google Ads API for each managed client account, scoped to the **last 7 days**:

| Metric | GAQL Field | Purpose |
|---|---|---|
| Impressions | `metrics.impressions` | Display in weekly report |
| Clicks | `metrics.clicks` | Display in weekly report |
| Click-through rate | `metrics.ctr` | Display in weekly report |
| Cost per click | `metrics.average_cpc` | Display in weekly report |
| Conversions | `metrics.conversions` | WhatsApp button click conversions |
| Cost per conversion | `metrics.cost_per_conversion` | Display in weekly report |
| Total spend | `metrics.cost_micros` | Display in weekly report |

### 3.2 GAQL Query Example

```sql
SELECT
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.average_cpc,
  metrics.conversions,
  metrics.cost_per_conversion,
  metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
```

### 3.3 Data Handling

- Metrics are fetched **on demand** when an agency staff member requests a report.
- Responses are cached **server-side in memory for 30 minutes** to avoid redundant API calls (same pattern already used for Meta Ads integration).
- No client data is written to a database or stored on disk.
- No data is transmitted to third parties.

---

## 4. Functionality Description

### 4.1 Weekly Report Generation

For each client account, Jake OS:
1. Fetches Google Ads metrics for the last 7 days via the API.
2. Combines them with Meta Ads metrics (already integrated).
3. Renders a pre-formatted weekly report text (in Brazilian Portuguese) containing both Google Ads and Meta Ads results side by side.
4. Allows the agency staff member to copy the report text to the clipboard with one click, for distribution via WhatsApp or internal messaging tools.

### 4.2 Accounts Managed

The agency manages Google Ads accounts for approximately **10–14 small and medium-sized local business clients** (fitness studios, dental clinics, legal firms, event companies, etc.). All accounts are managed under the agency's Google Ads Manager Account (MCC).

### 4.3 No Automated Actions

Jake OS performs **read-only** operations on Google Ads. It does **not**:
- Create, pause, or delete campaigns
- Modify bids or budgets
- Upload assets or audiences
- Make any write operations of any kind

---

## 5. Technical Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, Flask 3.x |
| Google Ads client | `google-ads` Python library (official) |
| Authentication | OAuth2 with offline refresh token |
| Hosting | Private VPS (single-tenant, agency-only access) |
| Frontend | Vanilla JavaScript SPA (no framework) |
| Session auth | Flask server-side sessions |

---

## 6. Security

- The developer token, OAuth2 client credentials, and refresh token are stored as **environment variables** on the server — never hardcoded or exposed to the browser.
- The application requires **authenticated login** before any API data can be accessed.
- All communication between the browser and the server uses **HTTPS**.
- The server is accessible only to agency staff.

---

## 7. Mockup — Report Output Example

Below is an example of the weekly report text generated by Jake OS after fetching both Meta Ads and Google Ads data:

```
Boa tarde pessoal!
Segue relatório das nossas campanhas nos últimos 7 dias:

Cliente: Isac Academia

Meta
👥 Alcance: 12.450
▶️ Cliques: 320
🎯 Mensagens iniciadas: 18
💰 Custo por mensagem: R$ 14,50

Google
👥 Impressões: 8.200
▶️ Cliques: 210
🎯 Conversão (Clique botão WhatsApp): 12
💰 Custo por conversão: R$ 9,80

* Seguimos com os testes e otimizações nas campanhas.
Precisamos de um feedback comercial para darmos os próximos passos 🙏

Boa semana a todos! 🙏
```

---

## 8. Summary

Jake OS is a **private, internal, read-only reporting tool** used exclusively by agency staff to compile and distribute weekly performance summaries for their clients' Google Ads and Meta Ads campaigns. The Google Ads API integration will be used solely to retrieve campaign metrics via GAQL queries, with no write access, no data storage, and no third-party data sharing.
