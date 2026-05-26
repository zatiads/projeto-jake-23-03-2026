/**
 * Script para adicionar leads novos na planilha Suprema Metal
 * Execute UMA VEZ clicando em Executar > adicionar_leads
 *
 * Como usar:
 * 1. Na planilha, vá em Extensões > Apps Script
 * 2. Cole este código no editor
 * 3. Clique em "Executar" (função: adicionar_leads)
 * 4. Autorize quando pedido
 */

function adicionar_leads() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Todos os leads");
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Aba 'Todos os leads' não encontrada!");
    return;
  }

  // Novos leads ordenados do mais recente para o mais antigo
  // Formato: [Data, Nome, Telefone, E-mail, Cidade, Serviço, Mensagem, Origem, Canal, Dispositivo, Status]
  var novosLeads = [
    ["25/05/2026 11:56", "Luis Felipe",                              "(16) 99286-1506", "luis.ccosta91@gmail.com",              "São Joaquim da Barra", "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Desktop", "Novo"],
    ["25/05/2026 07:00", "BRUNO SILVA",                              "(47) 93383-8755", "jacomelly1984@gmail.com",              "Itajaí",               "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["24/05/2026 18:52", "Raquel Alves",                             "(31) 99192-6198", "raquelalvesouza@icloud.com",           "Belo Horizonte",       "Caçambas",           "Recolher resto de obra",                                                                        "Formulário","Google Ads", "Mobile",  "Novo"],
    ["24/05/2026 02:47", "Marcos",                                   "(21) 97765-7070", "medeirosmetais@gmail.com",             "Rio de Janeiro",       "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["23/05/2026 13:50", "MARCELO EDUARDO CITRANGULO DOS REIS",      "(12) 97402-6732", "cacambamr@gmail.com",                  "Taubaté",              "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["23/05/2026 11:01", "Simone",                                   "(42) 99943-9843", "simonenett@hotmail.com",               "Guarapuava",           "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["22/05/2026 21:26", "ROBLEDO RESENDE",                          "(62) 99285-0885", "r2distribuicao@gmail.com",             "Caldas Novas",         "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["22/05/2026 21:13", "Wolmer",                                   "(67) 99607-2377", "wolcampa@gmail.com",                   "Dourados MS",          "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["22/05/2026 17:42", "Marianna",                                 "(43) 99111-4602", "mariannaperez1982@yahoo.com",          "Marianna",             "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["22/05/2026 12:02", "Rodolfo Decresci",                         "(11) 98989-2268", "rodolfo.decresci@orizonvr.com.br",    "São Paulo",            "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Desktop", "Novo"],
    ["22/05/2026 09:36", "JOAO",                                     "(96) 98112-6997", "juniorjspj@unifap.br",                 "Macapá",               "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 22:10", "Brenno",                                   "(21) 99390-0707", "sbrennosantos1@icloud.con",            "Rio de Janeiro",       "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 18:55", "Érica Portilho",                           "(62) 99337-8746", "eng.erica.portilho@efort.org.br",     "Goiânia",              "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Desktop", "Novo"],
    ["21/05/2026 18:43", "DIVINO José Nunes Borges",                 "(64) 99611-5163", "divinofenixnunes@gmail.com",           "Orizona",              "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 18:40", "Secretaria do Meio Ambiente de Orizona",   "(64) 99611-5163", "divinofenixnunes@gmail.com",           "Orizona",              "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 18:25", "Érica Rizzo",                              "(62) 99337-8746", "erica.portilho@efort.org.br",          "Goiânia",              "Containers de Lixo", "Gostaria de orçamentos dos Containers de aço para lixo que vocês possuem",                      "Formulário","Google Ads", "Desktop", "Novo"],
    ["21/05/2026 16:37", "douglas parizi gaspar",                    "(35) 99130-8655", "manaca.amb@gmail.com",                 "Muzambinho",           "Containers de Lixo", "conteiner 1200l",                                                                               "Formulário","Google Ads", "Desktop", "Novo"],
    ["21/05/2026 16:03", "netto",                                    "(82) 99669-0906", "adeval.netto@sbvengenharia.com",       "Maceió",               "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Desktop", "Novo"],
    ["21/05/2026 14:38", "Ademir",                                   "(38) 99918-9426", "ademircardoso163@gmail.com",           "Montes Claros",        "",                   "",                                                                                              "WhatsApp",  "Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 14:37", "Ademir Cardoso de Souza",                  "(38) 99918-9426", "ademircardoso163@gmail.com",           "Montes Claros",        "Caçambas",           "Queria saber o preço casanba de emtuliho",                                                      "Formulário","Google Ads", "Mobile",  "Novo"],
    ["21/05/2026 11:00", "Marielly Marques da Silva",                "(62) 99981-8529", "mariellymarques068@gmail.com",         "Uruaçu",               "Containers de Lixo", "Alugar",                                                                                        "Formulário","Google Ads", "Mobile",  "Novo"],
    ["20/05/2026 23:05", "Aluízio",                                  "(75) 99981-3604", "castoriraquara@hotmail.com",           "Iraquara, Bahia",      "Caçambas",           "Gostaria de saber o valor de 01 caçamba estacionária p/ poliguindaste de 5mt³ entregue no cep 46980-000?", "Formulário","Google Ads", "Mobile","Novo"],
  ];

  // Encontra a linha do cabeçalho dos leads (busca pela coluna "Nome")
  var allData = sheet.getDataRange().getValues();
  var headerRow = -1;
  for (var i = 0; i < allData.length; i++) {
    if (allData[i][2] === "Nome" && allData[i][1] === "Data") {
      headerRow = i + 1; // 1-indexed
      break;
    }
  }

  if (headerRow === -1) {
    SpreadsheetApp.getUi().alert("Cabeçalho da tabela de leads não encontrado!");
    return;
  }

  // Insere as linhas logo após o cabeçalho (posição headerRow + 1)
  var insertRow = headerRow + 1;
  sheet.insertRows(insertRow, novosLeads.length);

  // Preenche os dados (coluna B=Data, C=Nome, D=Telefone, E=E-mail, F=Cidade, G=Serviço, H=Mensagem, I=Origem, J=Canal, K=Dispositivo, L=Status)
  // Coluna A = # (número sequencial, será atualizado no final)
  for (var j = 0; j < novosLeads.length; j++) {
    var row = insertRow + j;
    sheet.getRange(row, 2, 1, 11).setValues([novosLeads[j]]);
  }

  // Renumera TODOS os leads da coluna A (do primeiro lead até o último)
  var lastRow = sheet.getLastRow();
  var numero = 1;
  for (var k = headerRow + 1; k <= lastRow; k++) {
    var rowData = sheet.getRange(k, 2).getValue();
    if (rowData !== "") { // só numera linhas com data preenchida
      sheet.getRange(k, 1).setValue(numero);
      numero++;
    }
  }

  SpreadsheetApp.getUi().alert("✅ " + novosLeads.length + " leads adicionados com sucesso!");
}
