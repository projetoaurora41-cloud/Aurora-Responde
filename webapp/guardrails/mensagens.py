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

MSG_ALICIAMENTO = (
    "Você não tem culpa disso, e fez bem em contar.\n\n"
    "**Não envie fotos nem vídeos** e não continue a conversa com essa pessoa. "
    "Se puder, guarde as mensagens (prints) como prova, sem apagar nada.\n\n"
    "**Conte agora para um adulto de confiança** (mãe, pai, responsável, professor "
    "ou alguém da escola).\n\n"
    "Ligue para o **Disque 100** (gratuito, pode ser anônimo, 24 horas). "
    "**Se você estiver em perigo agora, ligue 190.** Você também pode procurar o "
    "**Conselho Tutelar** da sua cidade.\n\n"
    "Pedir ou oferecer dinheiro a uma criança ou adolescente em troca de fotos é "
    "**crime** (ECA, arts. 240 e 241-D)."
)

MSG_COMO_DENUNCIAR = (
    "O Aurora **não recebe denúncias**. Para denunciar violência contra criança ou "
    "adolescente, use os canais oficiais:\n\n"
    "- **Disque 100** — gratuito, anônimo e 24 horas, atendido pela Ouvidoria "
    "Nacional de Direitos Humanos. Também recebe denúncias pelo site "
    "gov.br/pt-br/servicos/denunciar-violacao-de-direitos-humanos.\n"
    "- **Conselho Tutelar** do município — aplica as medidas de proteção à criança "
    "ou ao adolescente.\n"
    "- **190 (Polícia Militar)** — em emergência ou se a violência estiver "
    "acontecendo agora.\n\n"
    "Você também pode registrar um **boletim de ocorrência** na delegacia (de "
    "preferência a especializada na proteção da criança e do adolescente) ou pela "
    "delegacia eletrônica do seu estado."
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
