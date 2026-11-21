# Central de Vagas

Aplicacao local e multi-perfil para encontrar vagas de acordo com cada pessoa. Ela consulta fontes publicas, calcula uma pontuacao explicavel e mantem o historico separado por perfil.

## O que faz

- Cadastro simples de qualquer area: cargos desejados, habilidades, localidade, modalidade e senioridade.
- Busca Remotive (remotas), Greenhouse e Lever (empresas configuradas), e Adzuna quando houver chaves proprias.
- Mostra por que cada vaga recebeu a nota e permite salvar status: salvar, revisar, candidatura enviada ou descartar.
- Guarda dados localmente em `data/central_vagas.sqlite3`; nao coleta credenciais de LinkedIn, Gupy ou e-mail.

## Como iniciar no Windows

No PowerShell, dentro desta pasta:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

O navegador abre em `http://localhost:8501`. Para encerrar, use `Ctrl+C` no terminal.

## Atualização automática

A atualização diária já foi instalada neste computador para as **08:00**. Ela consulta as vagas públicas em São Paulo e grava apenas as novas no painel. O computador precisa estar ligado e a sessão do Windows aberta nesse horário. Para instalar novamente em outro computador, execute `instalar_atualizacao_diaria.ps1` após rodar o projeto uma vez. O registro fica em `data/daily_scan.log`.

## Fontes e limites

Remotive fica habilitada para vagas remotas. Greenhouse e Lever exigem o identificador publico da pagina de carreiras da empresa; informe um por linha na tela. Para usar Adzuna, crie chaves em https://developer.adzuna.com/ e informe-as em **Fontes de vagas**. As fontes podem limitar consultas, portanto use buscas pontuais, nao atualizacao continua.

## Privacidade e limites

O app nao se candidata, nao envia curriculos e nao tenta preencher formularios, CAPTCHAs ou areas autenticadas. Abrir a vaga leva a pessoa ao site original, onde ela decide se quer se candidatar. A pontuacao e uma ajuda de triagem, nao uma decisao automatica.
