# Central de Vagas

Encontre vagas em São Paulo, no Brasil e remotas a partir do perfil profissional. A Central de Vagas organiza oportunidades públicas, destaca as mais compatíveis e permite acompanhar candidaturas sem automatizar envios.

Aplicacao local e multi-perfil para encontrar vagas de acordo com cada pessoa. Ela consulta fontes publicas, calcula uma pontuacao explicavel e mantem o historico separado por perfil.

## O que faz

- Cadastro simples de qualquer area: cargos desejados, habilidades, localidade, modalidade e senioridade.
- Busca automática nas páginas públicas do Grupo Fleury, Dasa, Eurofarma e Rede D'Or, além de Remotive, Greenhouse e Lever (quando configurados) e Adzuna opcional.
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

O repositório também possui o workflow **Atualizar catálogo de vagas** em GitHub Actions. Ele roda diariamente às 08:00 (Brasília), atualiza `data/vagas_publicas.json` e envia o catálogo ao repositório. Uma versão hospedada do app carrega esse arquivo automaticamente; os perfis e status pessoais continuam locais até uma futura migração para um banco em nuvem.

## Fontes e limites

O agente prioriza oportunidades publicadas para São Paulo - SP. O Grupo Fleury cobre marcas como Fleury, a+, Hermes Pardini e Genesis. Dasa, Eurofarma e Rede D'Or são consultadas através de suas páginas públicas de carreira. A aba **Fontes de saúde** mantém o catálogo das 29 instituições prioritárias; fontes sem feed público estável ficam registradas para acompanhamento, sem contornar login, CAPTCHA ou áreas privadas.

## Privacidade e limites

O app nao se candidata, nao envia curriculos e nao tenta preencher formularios, CAPTCHAs ou areas autenticadas. Abrir a vaga leva a pessoa ao site original, onde ela decide se quer se candidatar. A pontuacao e uma ajuda de triagem, nao uma decisao automatica.

## Termos e privacidade

A aba **Termos e privacidade** informa os limites do serviço e permite excluir perfis salvos com seu histórico de vagas e status.

- A aplicação organiza vagas públicas, mas não garante contratação nem disponibilidade das oportunidades.
- Não envia currículos, não realiza candidaturas automaticamente e não preenche formulários de terceiros.
- Os perfis e os status de vagas ficam no banco SQLite da instalação (`data/central_vagas.sqlite3`): no computador onde o aplicativo roda ou no servidor de uma implantação hospedada. O usuário é responsável pelo que cadastra.
- Links e descrições pertencem às fontes originais, que podem modificar ou retirar as vagas.
- O PIX é apoio voluntário: não representa compra, não prevê reembolso nem é exigido para usar o sistema ou obter benefícios.
- É possível excluir um perfil e todo o histórico vinculado pela aba. Para limpar o banco inteiro de uma instalação local própria, feche o aplicativo e remova `data/central_vagas.sqlite3`; ele será recriado vazio. Apagar apenas o cache do navegador não exclui os dados do banco.

**Atenção:** não inclua documentos, senhas ou dados sensíveis além do necessário no perfil.

Um perfil novo só é gravado após clicar em **Salvar alterações do perfil**.
