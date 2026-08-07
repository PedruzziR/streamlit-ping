# Política de segurança

Este repositório é **público** e possui secrets de produção configurados em
`Settings > Secrets and variables > Actions`:

| Secret | Conteúdo | Alcance |
|---|---|---|
| `SUPABASE_URL` | URL do projeto Supabase | — |
| `SUPABASE_SERVICE_KEY` | chave `service_role` | **ignora RLS: lê e escreve em todas as tabelas do projeto** |

A `service_role` dá acesso irrestrito ao banco, incluindo tabelas de outros
aplicativos que não têm relação com este ping. Toda a política abaixo existe
por causa disso.

---

## PROIBIDO: `pull_request_target` e `issue_comment`

**Nenhum workflow deste repositório pode usar os gatilhos
`pull_request_target` ou `issue_comment`.** Sem exceção, sem "só para testar".

### Por quê

Em repositório público, qualquer pessoa abre um pull request ou comenta numa
issue. A diferença entre os gatilhos é quem tem acesso aos secrets:

| Gatilho | Contexto de execução | Recebe secrets? |
|---|---|---|
| `pull_request` | fork, sem privilégios | **Não** |
| `pull_request_target` | repositório base, com privilégios | **Sim** |
| `issue_comment` | repositório base, com privilégios | **Sim** |

`pull_request_target` roda no contexto do repositório base — com os secrets
disponíveis — mas foi desenhado para reagir a código enviado por terceiros. Se
esse workflow fizer checkout do código do PR (`ref: refs/pull/N/merge`) e
executar qualquer coisa dele — um script, um `npm install` com `postinstall`,
uma dependência do `requirements.txt` — o atacante executa código arbitrário
com a `service_role` no ambiente. Ele nem precisa que o PR seja aprovado ou
mergeado: basta abri-lo.

`issue_comment` tem o mesmo problema por outro caminho: dispara com privilégios
a partir de um comentário que qualquer pessoa escreve.

Não existe uso desses gatilhos neste repositório que compense o risco. Se algum
dia for realmente necessário automatizar algo em PRs, use `pull_request` (sem
secrets) ou um workflow separado com `workflow_run`.

### Gatilhos permitidos

- `schedule`
- `workflow_dispatch`
- `push` (restrito a branches do próprio repositório)

## Demais regras

- **Nunca** escrever credenciais no código. Tudo vem de `os.environ`
  (ver `streamlit_ping.py`).
- **Nunca** imprimir o valor de um secret em log. Logs de Actions em repositório
  público são visíveis para qualquer pessoa. O mascaramento automático do GitHub
  é uma rede de proteção, não uma garantia — ele falha com valores transformados
  (base64, fatiados, interpolados).
- Configurações recomendadas em `Settings > Actions > General`:
  - *Fork pull request workflows*: exigir aprovação para **todos** os
    colaboradores externos
  - *Workflow permissions*: **read-only** por padrão (o `keepalive.yml` declara
    o `actions: write` de que precisa no próprio job)
  - **Secret scanning** e **push protection** ativados

## Mitigação pendente (opcional)

O script executa uma única operação no Supabase: `INSERT` em
`streamlit_ping_log`. Não precisa de `service_role`. Trocar pela chave `anon`
com uma policy de RLS restrita a insert nessa tabela reduziria o pior cenário de
"banco inteiro comprometido" para "linhas de lixo na tabela de log". Enquanto
essa troca não for feita, a proibição acima é a única barreira.
