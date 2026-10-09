"""Mensagens canônicas do pipeline de guardrails."""

_BO = (
    "**Procure imediatamente uma delegacia** (de preferência a Delegacia de "
    "Proteção à Criança e ao Adolescente) para **registrar um boletim de "
    "ocorrência (B.O.)**, ou registre o B.O. **online** pela Delegacia Eletrônica "
    "do seu estado. Maus-tratos, abuso, agressão e exploração são **crimes**, e o "
    "B.O. formaliza a denúncia e permite a investigação policial."
)

MSG_DISQUE_100 = (
    "**Se há perigo imediato, ligue agora para o 190** (Polícia Militar).\n\n"
    + _BO
    + "\n\nVocê também pode ligar para o **Disque 100** (telefone 100) — "
    "denúncia anônima, gratuita e 24 horas — e, se for criança ou adolescente, "
    "procurar o **Conselho Tutelar** do município.\n\n"
    "O Aurora Responde trata de dados e legislação; não substitui o atendimento "
    "policial, de proteção ou de acolhimento."
)

MSG_CONSELHO_TUTELAR = (
    "**Se há perigo imediato, ligue agora para o 190** (Polícia Militar).\n\n"
    + _BO
    + "\n\nDepois, ou em paralelo, procure o **Conselho Tutelar** do município "
    "— órgão local responsável por aplicar medidas de proteção quando direitos "
    "de crianças e adolescentes são ameaçados ou violados — e, se preferir, "
    "denuncie de forma anônima no **Disque 100** (telefone 100), gratuito e 24 "
    "horas.\n\n"
    "O Aurora Responde trata de dados e legislação; não substitui o atendimento "
    "da delegacia, do Conselho Tutelar nem de outros serviços de proteção."
)

MSG_INJECAO = (
    "Não posso seguir instruções que tentam alterar meu papel ou ignorar as "
    "regras deste assistente. Reformule a pergunta sobre dados de violência, "
    "legislação relacionada ou o funcionamento da plataforma Aurora."
)

MSG_SAIDA_BLOQUEADA = (
    "A resposta foi bloqueada pelos filtros de segurança (possível vazamento "
    "técnico ou conteúdo sensível). Reformule a pergunta ou tente novamente."
)

MSG_SUPRESSAO = (
    "O número encontrado está abaixo do limiar de divulgação adotado para "
    "proteção estatística. Não é possível detalhar essa contagem aqui."
)
