# Instruções do repositório

Monitor de ping que mantém os apps do Streamlit Community Cloud acordados.
Roda no GitHub Actions a cada 15 minutos.

## Regra inegociável

**Nunca adicione os gatilhos `pull_request_target` ou `issue_comment` a nenhum
workflow deste repositório.** O repositório é público e tem a `service_role` do
Supabase nos secrets; esses dois gatilhos expõem os secrets a código enviado por
qualquer pessoa de fora. Motivo detalhado em [SECURITY.md](SECURITY.md).

Gatilhos permitidos: `schedule`, `workflow_dispatch`, `push`.

Se uma tarefa parecer exigir um desses gatilhos proibidos, pare e pergunte ao
usuário em vez de adicionar.

## Outras notas

- O cron de 15 minutos é intencional e foi validado empiricamente: os apps
  hibernam em ~30 minutos ou menos. Não reduza a frequência "para economizar" —
  o repositório é público e os minutos de Actions são ilimitados.
- Workflows agendados são desativados pelo GitHub após 60 dias sem atividade no
  repositório. Só um push reinicia esse contador; religar o workflow pelo botão
  da interface **não** reinicia.
- Credenciais sempre via `os.environ`. Nunca hardcoded, nunca em log.
