# webhook-log-audit

Lê um log de entregas de webhook (JSONL) e aponta problemas de integração: evento aplicado duas vezes, evento fora de ordem, buraco na sequência, evento sem assinatura válida que mesmo assim foi processado, retry rápido demais e evento que nunca deu certo.

Independent demo, not affiliated with FCamara. (Demo independente, sem ligação com a FCamara.) Feita por Lucas Saldanha Werneck para mostrar como eu olho para integrações por mensageria. Todos os dados do exemplo são inventados.

## Por que existe

Webhook entrega "pelo menos uma vez". Isso significa que o mesmo evento chega duas vezes, ou chega fora de ordem. Quem consome precisa ser idempotente. Num sistema real, eu confiro isso olhando o log. Esta ferramenta faz essa conferência em poucos segundos.

## Como rodar

Python 3.10 ou mais novo. Não tem dependência para rodar.

```
python -m eventlog_audit examples/sample-events.jsonl
python -m eventlog_audit meu-log.jsonl --fail-on-high   # sai com código 1 se houver achado grave
```

Cada linha do arquivo é um JSON com: `event_id`, `resource_id`, `seq`, `ts` (segundos), `signature_ok` (true/false) e `outcome` (`processed`, `ignored` ou `failed`).

## O que ela verifica

| Verificação | Gravidade | Regra |
|---|---|---|
| double-processed | alta | o mesmo `event_id` com mais de um `processed` |
| unsigned-processed | alta | `processed` com `signature_ok` falso |
| never-succeeded | alta | todas as tentativas do evento falharam |
| out-of-order | média | por recurso, um `seq` menor aplicado depois de um maior |
| gap | média | por recurso, número de `seq` que nunca foi aplicado entre dois aplicados |
| fast-retry | baixa | duas tentativas do mesmo evento com menos de 1 s entre elas |

## Rodar os testes

```
pip install pytest
python -m pytest -q
```

## What was tested

- 15 testes automáticos, todos offline, rodando no GitHub Actions a cada push.
- Cada verificação tem um caso que deve achar e um que não deve achar (por exemplo, duplicata ignorada corretamente não é achado).
- O arquivo de exemplo tem 16 entregas com um problema plantado de cada tipo. Os testes conferem que a ferramenta acha exatamente esses seis.
- O código de saída da linha de comando (0, 1 e 2).

## What was not tested

- Nenhum log real. Só os dados inventados em `examples/`.
- Arquivos grandes: tudo é lido em memória.
- Relógios diferentes entre sistemas. A ordem usa o campo `ts` como vem.
- Formatos de log de provedores específicos. O formato JSONL acima é um contrato próprio, simples.
- Eventos sem `seq`: eles entram nas verificações de duplicata, assinatura e retry, mas não nas de ordem e buraco.
