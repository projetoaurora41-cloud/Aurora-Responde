"""FAQ da seção Perguntas Frequentes (espelha prototype_02/src/data/faq.ts)."""

from __future__ import annotations

import math
import re


def partes_fonte(texto: str) -> list[dict]:
    """Quebra a fonte em segmentos de texto e URL (como no protótipo)."""
    partes: list[dict] = []
    for p in re.split(r"(https?://[^\s)]+)", texto or ""):
        if not p:
            continue
        if re.match(r"^https?://", p):
            href = re.sub(r"[.;]$", "", p)
            partes.append({"tipo": "url", "texto": p, "href": href})
        else:
            partes.append({"tipo": "texto", "texto": p})
    return partes


ITENS_FAQ: list[dict] = [
    {
        "n": 1,
        "pergunta": 'Como agir diante da suspeita de que uma criança ou adolescente está sendo vítima de exploração sexual?',
        "resposta": 'Comunique a suspeita imediatamente. O principal canal é o Disque 100. Você também pode procurar o Conselho Tutelar do município ou uma delegacia de polícia. Em casos de urgência ou crime em flagrante, ligue 190 (Polícia Militar). Não é necessário ter provas; a suspeita já obriga a comunicação aos órgãos de proteção.',
        "fonte": 'Estatuto da Criança e do Adolescente (ECA), art. 13 (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Página oficial do Disque 100 (MDHC) (https://www.gov.br/pt-br/servicos/denunciar-violacao-de-direitos-humanos).',
        "validado": True,
    },
    {
        "n": 2,
        "pergunta": 'Sou adolescente e estão me forçando ou oferecendo dinheiro/presentes em troca de sexo ou fotos. O que eu faço?',
        "resposta": 'Peça ajuda. Você não tem culpa de nada disso. Ligue para o Disque 100 (é gratuito, funciona 24 horas e pode ser anônimo) ou mande mensagem para o WhatsApp do Disque 100. Se estiver em perigo agora, ligue 190. Você também pode contar para um professor, psicólogo da escola ou ir ao Conselho Tutelar. O consentimento de menores de 18 anos nessas situações não tem validade legal.',
        "fonte": 'ECA (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Página do Disque 100 (https://www.gov.br/pt-br/servicos/denunciar-violacao-de-direitos-humanos).',
        "validado": True,
    },
    {
        "n": 3,
        "pergunta": 'Onde e como posso denunciar casos de exploração sexual infantil?',
        "resposta": 'A denúncia pode ser feita pelo Disque 100 (telefone, WhatsApp, Telegram, site ou videochamada em Libras). Outros canais incluem o Conselho Tutelar, as Delegacias Especializadas de Proteção à Criança e ao Adolescente (DPCA), delegacias comuns, Ministério Público e o aplicativo Direitos Humanos Brasil.',
        "fonte": 'Portal Gov.br (Denunciar violação de direitos humanos) (https://www.gov.br/pt-br/servicos/denunciar-violacao-de-direitos-humanos); MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 4,
        "pergunta": 'A denúncia de exploração sexual pode ser feita de forma anônima?',
        "resposta": 'Sim. O Disque 100 garante o anonimato de quem denuncia. As informações do denunciante são mantidas em absoluto sigilo, e apenas os dados sobre a possível violação são encaminhados aos órgãos competentes para investigação e proteção.',
        "fonte": 'MDHC - FAQ Disque 100 (https://www.gov.br/mdh/pt-br/acesso-a-informacao/disque-100/disque-100).',
        "validado": False,
    },
    {
        "n": 5,
        "pergunta": 'O que acontece após uma denúncia ser feita no Disque 100?',
        "resposta": 'A central recebe, analisa e encaminha a denúncia aos órgãos de proteção (Conselho Tutelar) e de responsabilização (Polícia Civil, Ministério Público). A pessoa que denunciou recebe um número de protocolo e pode acompanhar o andamento. O objetivo é duplo: investigar o agressor e iniciar imediatamente a proteção da vítima por meio da rede de assistência.',
        "fonte": 'MDHC - Fluxo de denúncias (https://www.gov.br/mdh/pt-br/ondh).',
        "validado": False,
    },
    {
        "n": 6,
        "pergunta": 'Profissionais (professores, médicos, psicólogos) são obrigados a denunciar suspeitas de exploração sexual?',
        "resposta": 'Sim. A notificação é compulsória. O ECA prevê multa para profissionais de saúde, educação ou assistência que deixarem de comunicar à autoridade competente os casos de suspeita ou confirmação de maus-tratos, abusos ou exploração sexual.',
        "fonte": 'ECA, arts. 13 e 245 (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Lei 13.431/2017 (https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm).',
        "validado": False,
    },
    {
        "n": 7,
        "pergunta": 'A Plataforma Aurora recebe denúncias de exploração sexual?',
        "resposta": 'Não. A Plataforma Aurora consolida dados públicos para orientar políticas públicas, mas não é um canal de denúncia. O próprio sistema Aurora orienta o usuário a buscar imediatamente o Disque 100, Conselho Tutelar ou o 190.',
        "fonte": 'Objeto do Projeto Aurora.',
        "validado": True,
    },
    {
        "n": 8,
        "pergunta": 'O que fazer se encontrar imagens de abuso ou exploração sexual infantil na internet?',
        "resposta": 'Não baixe nem compartilhe o conteúdo, pois isso também é crime. Copie a URL (link) da página ou o número de contato (em caso de aplicativos de mensagem) e denuncie em plataformas como a SaferNet Brasil (Canal de Denúncias), no Disque 100 ou em delegacias de crimes cibernéticos.',
        "fonte": 'SaferNet Brasil (https://new.safernet.org.br/denuncie); Lei 8.069/1990 (ECA) (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Delegacia Virtual (https://delegaciavirtual.sinesp.gov.br/portal/).',
        "validado": False,
    },
    {
        "n": 9,
        "pergunta": 'Quem é o responsável legal por investigar os crimes de exploração sexual?',
        "resposta": 'A investigação criminal cabe à Polícia Civil (por meio das DPCAs, onde houver) e à Polícia Federal, especialmente quando envolver pornografia infantil na internet (crimes transnacionais) ou redes de tráfico internacional. A responsabilização penal é promovida pelo Ministério Público.',
        "fonte": 'Constituição Federal (https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm); ECA (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 10,
        "pergunta": 'Se o suspeito for um familiar, como devo agir?',
        "resposta": 'A denúncia deve ser feita da mesma forma (Disque 100, Conselho Tutelar). O fato de o agressor ser familiar não impede a denúncia e agrava a pena do crime. Os órgãos de proteção afastarão o agressor do convívio da criança, garantindo a segurança da vítima.',
        "fonte": 'ECA (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Código Penal (https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm).',
        "validado": False,
    },
    {
        "n": 11,
        "pergunta": 'O que é a exploração sexual de crianças e adolescentes?',
        "resposta": 'É o uso de crianças e adolescentes para fins de satisfação sexual atrelado a uma relação de mercantilização. Envolve a troca (prometida ou real) de dinheiro, presentes, favores, alimentos ou moradia. É uma grave violação de direitos humanos que trata a vítima como objeto de lucro.',
        "fonte": 'Ministério da Saúde (Linha de cuidado) (https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/s/saude-da-crianca/publicacoes/linha-de-cuidado-para-a-atencao-integral-a-saude-de-criancas-adolescentes-e-suas-familias-em-situacao-de-violencias-orientacao-para-gestores-e-profissionais-de-saude/view); MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 12,
        "pergunta": 'Qual a diferença entre abuso sexual e exploração sexual?',
        "resposta": 'O abuso sexual ocorre quando a criança/adolescente é usada para a estimulação sexual do agressor, baseando-se em relações de poder e força. A exploração sexual inclui o fator da "mercantilização", ou seja, há uma troca de vantagens (dinheiro, bens, favores) e o envolvimento de terceiros (aliciadores, redes).',
        "fonte": 'Caderno de Atenção Básica (Ministério da Saúde) (https://bvsms.saude.gov.br/bvs/publicacoes/cadernos_atencao_basica_31_violencias.pdf).',
        "validado": False,
    },
    {
        "n": 13,
        "pergunta": 'A prostituição de adolescentes acima de 14 anos é crime?',
        "resposta": 'Sim. No Brasil, não existe "prostituição" de menores de 18 anos; o termo legal e técnico é exploração sexual de crianças e adolescentes. Induzir, atrair ou facilitar a prostituição ou exploração de menores de 18 anos é crime gravíssimo.',
        "fonte": 'ECA, art. 244-A (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm); Código Penal, art. 218-B (https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm).',
        "validado": False,
    },
    {
        "n": 14,
        "pergunta": 'A criança ou adolescente explorado sexualmente comete algum crime?',
        "resposta": 'Nunca. A criança ou o adolescente é sempre a vítima. A legislação brasileira e os tratados internacionais estabelecem que eles não possuem capacidade plena para consentir, independentemente da idade (desde que menores de 18 anos).',
        "fonte": 'ECA; Doutrina de Proteção Integral. (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm)',
        "validado": False,
    },
    {
        "n": 15,
        "pergunta": 'Quais são os principais crimes previstos no ECA relacionados à exploração sexual?',
        "resposta": 'O ECA tipifica crimes como: submeter à prostituição ou exploração (Art. 244-A), produzir, reproduzir, dirigir, fotografar, filmar cenas de sexo explícito ou pornográfico envolvendo criança/adolescente (Art. 240), e armazenar esse material (Art. 241-B).',
        "fonte": 'ECA, Título VII, Capítulo I (Dos Crimes em Espécie) (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 16,
        "pergunta": 'Exploração sexual de crianças e adolescentes é crime hediondo?',
        "resposta": 'Sim. A Lei 14.811/2024 e o Código Penal incluem crimes ligados à exploração sexual, tráfico de pessoas para esse fim, favorecimento da prostituição de crianças e adolescentes e a produção/armazenamento de pornografia infantil na lista de crimes hediondos.',
        "fonte": 'Lei 8.072/1990 (Lei dos Crimes Hediondos). (https://www.planalto.gov.br/ccivil_03/leis/l8072.htm; https://www.planalto.gov.br/ccivil_03/_Ato2023-2026/2024/Lei/L14811.htm)',
        "validado": True,
    },
    {
        "n": 17,
        "pergunta": 'O que é pornografia infantil à luz da legislação brasileira?',
        "resposta": 'Qualquer registro de cena de sexo explícito ou pornográfica envolvendo criança ou adolescente, seja por foto, vídeo, áudio ou transmissão ao vivo. A produção, compartilhamento, venda e o simples armazenamento são crimes.',
        "fonte": 'ECA, arts. 240, 241, 241-A e 241-B (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 18,
        "pergunta": 'O que é o turismo sexual?',
        "resposta": 'É a organização ou facilitação de viagens (nacionais ou internacionais) com o propósito principal de realizar a exploração sexual de crianças e adolescentes. Agências de turismo, hotéis e motoristas que facilitam ou lucram com essa prática cometem crime.',
        "fonte": 'Código Penal (https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm); MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 19,
        "pergunta": 'Um hotel ou motel pode hospedar crianças e adolescentes livremente?',
        "resposta": 'Não. É proibida a hospedagem de criança ou adolescente em hotel, motel, pensão ou similar, salvo se autorizado ou acompanhado pelos pais ou responsável. A violação gera multas e até fechamento do estabelecimento.',
        "fonte": 'ECA, arts. 82 e 250 (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 20,
        "pergunta": 'O pagamento em bens materiais descaracteriza a exploração sexual?',
        "resposta": 'Não. A exploração sexual não se configura apenas pela troca por dinheiro vivo. Presentes, roupas, celulares, comida, drogas ou até promessas de afeto ou falsos relacionamentos configuram o componente de troca mercantil da exploração.',
        "fonte": 'MDHC - Documentos de referência (https://www.gov.br/mdh/pt-br/campanha/maio-laranja/noticias-maio-laranja/maio-laranjagoverno-federal-conscientiza-a-populacao-para-enfrentamento-ao-abuso-e-a-exploracao-sexual).',
        "validado": False,
    },
    {
        "n": 21,
        "pergunta": 'Quais são os sinais de mudança comportamental que podem indicar exploração sexual?',
        "resposta": 'Depressão, isolamento, choro sem motivo aparente, agressividade repentina, transtornos alimentares, dificuldade de concentração, evasão escolar, comportamento sexualizado incompatível com a idade ou uso abusivo de álcool e drogas.',
        "fonte": 'Guia de Referência CREAS (https://www.mds.gov.br/webarquivos/publicacao/assistencia_social/Cadernos/orientacoes_creas.pdf); Ministério da Saúde (https://bvsms.saude.gov.br/).',
        "validado": False,
    },
    {
        "n": 22,
        "pergunta": 'Existem sinais físicos que indicam suspeita de abuso ou exploração?',
        "resposta": 'Sim. Sinais podem incluir: infecções sexualmente transmissíveis (ISTs), gravidez precoce, lesões na região genital ou anal, roupas rasgadas ou com sangue, dificuldade para andar ou sentar, e marcas físicas de violência (arranhões, hematomas).',
        "fonte": 'Linha de Cuidado - Ministério da Saúde (https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/s/saude-da-crianca/publicacoes/linha-de-cuidado-para-a-atencao-integral-a-saude-de-criancas-adolescentes-e-suas-familias-em-situacao-de-violencias-orientacao-para-gestores-e-profissionais-de-saude/view).',
        "validado": False,
    },
    {
        "n": 23,
        "pergunta": 'Quais sinais de alerta a escola deve observar?',
        "resposta": 'Queda brusca de rendimento, falta constante às aulas (evasão), cansaço extremo ou sono em sala de aula, posse de itens de valor (celulares, roupas novas) sem explicação de origem condizente com a renda familiar, ou contato com adultos desconhecidos na porta da escola.',
        "fonte": 'Caderno ECA na Escola (https://www.gov.br/mec/pt-br).',
        "validado": False,
    },
    {
        "n": 24,
        "pergunta": 'O que a área de saúde pode observar no atendimento?',
        "resposta": 'Além das lesões e infecções, a saúde deve observar se o acompanhante fala pela vítima, se há discrepância entre a idade da vítima e a do "parceiro/responsável" presente, e o estado emocional durante os exames.',
        "fonte": 'Protocolo de Atenção Integral - Ministério da Saúde (https://bvsms.saude.gov.br/bvs/publicacoes/protocolos_atencao_basica_saude_mulheres.pdf).',
        "validado": False,
    },
    {
        "n": 25,
        "pergunta": 'Como o uso da internet pode sinalizar vulnerabilidade à exploração?',
        "resposta": 'Tempo excessivo on-line em segredo, recebimento de presentes enviados por pessoas que a criança diz ser "amigos da internet", fechamento brusco da tela quando um adulto se aproxima, ou posse de múltiplos perfis ocultos em redes sociais.',
        "fonte": 'SaferNet Brasil (https://new.safernet.org.br/).',
        "validado": False,
    },
    {
        "n": 26,
        "pergunta": 'Crianças de áreas rurais ou rodovias têm riscos diferentes?',
        "resposta": 'Sim. Nesses contextos, a exploração frequentemente ocorre em postos de gasolina, paradas de caminhoneiros e pontos de prostituição nas margens das rodovias, muitas vezes disfarçada de venda de produtos ou pequenos serviços.',
        "fonte": 'Projeto Mapeamento de Pontos Vulneráveis nas Rodovias Federais (PRF/MPT) (https://www.childhood.org.br/acoes-e-iniciativas/childhood-brasil-e-prf-lancam-cartilha-do-projeto-mapear-2025-2026-com-avancos-no-combate-a-exploracao-sexual-de-criancas-e-adolescentes-nas-rodovias/).',
        "validado": False,
    },
    {
        "n": 27,
        "pergunta": 'Como a exploração sexual comercial no turismo se apresenta?',
        "resposta": 'Geralmente ocorre em regiões litorâneas, de grandes eventos ou turismo ecológico. Sinais incluem a presença constante de crianças/adolescentes não acompanhadas pelos pais circulando em hotéis, barracas de praia e barcos, em companhia de turistas.',
        "fonte": 'Programa Turismo Seguro (Ministério do Turismo) (https://www.gov.br/turismo/pt-br).',
        "validado": False,
    },
    {
        "n": 28,
        "pergunta": 'O que significa "grooming" (aliciamento on-line)?',
        "resposta": 'É a tática usada por abusadores na internet para ganhar a confiança da criança, do adolescente e de seus pais. O aliciador cria um vínculo emocional, muitas vezes fingindo ser da mesma idade, para posteriormente extorquir fotos íntimas ou marcar encontros presenciais.',
        "fonte": 'SaferNet Brasil (https://new.safernet.org.br/content/aliciamento-sexual-infantil-online).',
        "validado": False,
    },
    {
        "n": 29,
        "pergunta": 'A sextorsão faz parte da exploração sexual?',
        "resposta": 'Sim. Ocorre quando o agressor ameaça divulgar imagens íntimas da criança ou adolescente a menos que receba mais fotos, dinheiro ou favores sexuais. É uma forma de exploração que utiliza a extorsão como controle.',
        "fonte": 'SaferNet Brasil (https://new.safernet.org.br/); Código Penal (https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm).',
        "validado": False,
    },
    {
        "n": 30,
        "pergunta": 'Existe um perfil único de vítima de exploração sexual?',
        "resposta": 'Não. Qualquer criança ou adolescente pode ser vítima. No entanto, pobreza, histórico de violência doméstica, falta de estrutura familiar, racismo estrutural (maioria das vítimas são meninas negras) e abandono aumentam drasticamente a vulnerabilidade.',
        "fonte": 'Disque 100 - Dados abertos (https://www.gov.br/mdh/pt-br/ondh); MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 31,
        "pergunta": 'Como as famílias podem prevenir a exploração sexual no ambiente on-line?',
        "resposta": 'Acompanhando as atividades virtuais, configurando controles parentais, ensinando sobre privacidade on-line, orientando a não aceitar pedidos de amizade de desconhecidos e criando um ambiente de diálogo sem julgamentos para que a criança tenha coragem de relatar se algo estranho acontecer.',
        "fonte": 'Cartilha de Segurança para Internet (CGI.br) (https://cartilha.cert.br/).',
        "validado": False,
    },
    {
        "n": 32,
        "pergunta": 'Qual a importância da educação sexual nas escolas para a prevenção?',
        "resposta": 'O conhecimento adequado à faixa etária permite que a criança entenda o que é o toque adequado e inadequado, conheça seu corpo, aprenda a dizer "não" e saiba a quem recorrer caso sofra alguma violência. Informação é a primeira linha de defesa.',
        "fonte": 'Parâmetros Curriculares Nacionais (http://portal.mec.gov.br/seb/arquivos/pdf/livro101.pdf); MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 33,
        "pergunta": 'Como agir preventivamente em viagens com crianças?',
        "resposta": 'Garantir que a criança tenha sempre seus documentos (RG, certidão), orientá-la a procurar a polícia ou seguranças caso se perca, não deixá-la sozinha em hotéis ou locais públicos, e não entregar seus documentos a terceiros.',
        "fonte": 'MJSP - Cuidados em Viagens (https://www.gov.br/mj/pt-br).',
        "validado": False,
    },
    {
        "n": 34,
        "pergunta": 'O que é o "Maio Laranja" e o 18 de maio?',
        "resposta": 'O dia 18 de maio é o Dia Nacional de Combate ao Abuso e à Exploração Sexual de Crianças e Adolescentes. O "Maio Laranja" é a campanha nacional de mobilização e conscientização da sociedade para a denúncia e prevenção desses crimes.',
        "fonte": 'Lei 9.970/2000 (https://www.planalto.gov.br/ccivil_03/leis/l9970.htm).',
        "validado": False,
    },
    {
        "n": 35,
        "pergunta": 'Quais cuidados o comércio local (postos, hotéis) deve ter?',
        "resposta": 'Deve exigir documentação de crianças e adolescentes acompanhados de adultos, afixar placas com os números do Disque 100 e Conselho Tutelar (obrigatório em muitos estados), e treinar funcionários para identificar e denunciar suspeitas de exploração no estabelecimento.',
        "fonte": 'ECA; Legislações estaduais. (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm)',
        "validado": False,
    },
    {
        "n": 36,
        "pergunta": 'É seguro compartilhar rotinas de crianças nas redes sociais (sharenting)?',
        "resposta": 'O compartilhamento excessivo de fotos, fardamento escolar, horários e locais frequentados (geolocalização) expõe a criança a predadores, facilitando o aliciamento e o rastreamento físico. Recomenda-se configurar perfis como privados e limitar postagens de rotina.',
        "fonte": 'SaferNet; Guias de Segurança Cibernética. (https://new.safernet.org.br/)',
        "validado": False,
    },
    {
        "n": 37,
        "pergunta": 'Como ensinar a criança a pedir ajuda?',
        "resposta": 'Combine uma "palavra de segurança" familiar. Oriente sobre quais adultos de confiança (professores, diretores, médicos, policiais) ela pode procurar. Ensine o número do Disque 100 e do 190.',
        "fonte": 'Organizações de proteção à infância (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 38,
        "pergunta": 'Existe material do governo para ajudar na prevenção?',
        "resposta": 'Sim. O MDHC, o MJSP e o Ministério da Educação disponibilizam cartilhas, vídeos e guias informativos sobre prevenção à violência sexual, campanhas do 18 de maio e protocolos escolares.',
        "fonte": 'Portal do MDHC (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 39,
        "pergunta": 'O esporte e a cultura ajudam na prevenção?',
        "resposta": 'Sim. Projetos sociais, esportivos e culturais mantêm crianças e adolescentes ocupados em ambientes seguros, fortalecem redes de apoio e reduzem a vulnerabilidade socioeconômica que frequentemente antecede a exploração.',
        "fonte": 'Diretrizes de Assistência Social (https://www.gov.br/mds/pt-br).',
        "validado": False,
    },
    {
        "n": 40,
        "pergunta": 'A conscientização da comunidade é importante?',
        "resposta": 'Fundamental. A proteção da criança e do adolescente é dever da família, da sociedade e do Estado. A comunidade atua como uma rede de vigilância; quando os vizinhos sabem como e onde denunciar, as redes de exploração perdem força.',
        "fonte": 'Constituição Federal, Art. 227 (https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm); ECA, Art. 4º (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 41,
        "pergunta": 'O que é a Rede de Proteção à Criança e ao Adolescente?',
        "resposta": 'É o conjunto articulado de instituições governamentais (Saúde, Educação, Assistência Social, Segurança Pública, Justiça) e da sociedade civil (Conselhos, ONGs) que atuam integradas para garantir os direitos e proteger vítimas de violência.',
        "fonte": 'Sistema de Garantia de Direitos (SGD) (https://www.gov.br/mdh/pt-br).',
        "validado": False,
    },
    {
        "n": 42,
        "pergunta": 'Qual o papel do Conselho Tutelar no atendimento a vítimas?',
        "resposta": 'O Conselho não julga nem investiga o crime, mas aplica medidas de proteção imediata à vítima (como encaminhamento a serviços médicos e psicológicos, ou acolhimento institucional, se necessário) e requisita a intervenção do Estado para garantir a segurança da criança.',
        "fonte": 'ECA, arts. 131 e 136 (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 43,
        "pergunta": 'O que é o CREAS e qual o seu papel?',
        "resposta": 'O Centro de Referência Especializado de Assistência Social (CREAS) oferece serviços especializados e continuados (PAEFI) a famílias e indivíduos em situação de ameaça ou violação de direitos, incluindo atendimento psicossocial para vítimas de exploração sexual e suas famílias.',
        "fonte": 'Sistema Único de Assistência Social (SUAS) (https://www.mds.gov.br/webarquivos/publicacao/assistencia_social/Cadernos/orientacoes_creas.pdf).',
        "validado": False,
    },
    {
        "n": 44,
        "pergunta": 'A vítima precisará contar sua história repetidas vezes para a polícia e para o juiz?',
        "resposta": 'Não. A Lei 13.431/2017 criou o sistema de "Escuta Especializada" (na rede de proteção) e "Depoimento Especial" (na autoridade policial e judicial). O objetivo é que a criança seja ouvida em ambiente acolhedor, por profissionais treinados, gravando-se o depoimento para evitar a revitimização.',
        "fonte": 'Lei 13.431/2017 (https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm).',
        "validado": False,
    },
    {
        "n": 45,
        "pergunta": 'O que os serviços de saúde devem fazer imediatamente ao receber a vítima?',
        "resposta": 'Devem prestar o atendimento de emergência, oferecer a profilaxia pós-exposição ao HIV e outras ISTs, contracepção de emergência, tratamento de lesões físicas, notificar compulsoriamente o caso (inclusive no SINAN) e acionar a rede de proteção.',
        "fonte": 'Norma Técnica do Ministério da Saúde (https://bvsms.saude.gov.br/).',
        "validado": False,
    },
    {
        "n": 46,
        "pergunta": 'A criança vítima de exploração sexual precisará ser afastada da família?',
        "resposta": 'O acolhimento institucional (abrigo) ou familiar é uma medida extrema e excepcional, aplicada apenas quando a manutenção da criança na família de origem apresenta risco imediato à sua vida ou integridade (ex: os exploradores são os próprios pais).',
        "fonte": 'ECA (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 47,
        "pergunta": 'A família da vítima recebe algum tipo de apoio?',
        "resposta": 'Sim. A família (quando não envolvida na agressão) é considerada vítima indireta e deve ser acompanhada pelo CREAS para fortalecimento de vínculos, apoio psicológico e, se for o caso, inserção em programas de transferência de renda.',
        "fonte": 'SUAS; Guias de atendimento CREAS. (https://www.gov.br/mds/pt-br)',
        "validado": False,
    },
    {
        "n": 48,
        "pergunta": 'Se a criança ou adolescente estiver em outra cidade/estado sofrendo exploração, como ele retorna?',
        "resposta": 'A rede de proteção, através do Conselho Tutelar e da Assistência Social, articula o recâmbio (retorno seguro) da criança para sua comarca de origem e o acolhimento por sua família extensa ou abrigo local.',
        "fonte": 'Orientações técnicas do SUAS e CONANDA (https://www.gov.br/mdh/pt-br/acesso-a-informacao/participacao-social/conselho-nacional-dos-direitos-da-crianca-e-do-adolescente-conanda/conanda).',
        "validado": False,
    },
    {
        "n": 49,
        "pergunta": 'Como a Justiça da Infância e da Juventude atua nesses casos?',
        "resposta": 'A Justiça da Infância atua na aplicação das medidas de proteção mais gravosas (como o acolhimento institucional ou destituição do poder familiar), enquanto as Varas Criminais comuns (ou federais) processam e julgam os exploradores adultos.',
        "fonte": 'ECA (https://www.planalto.gov.br/ccivil_03/leis/l8069.htm).',
        "validado": False,
    },
    {
        "n": 50,
        "pergunta": 'Existe algum programa de proteção à vida para a vítima ameaçada de morte pela rede de exploração?',
        "resposta": 'Sim. O Programa de Proteção a Crianças e Adolescentes Ameaçados de Morte (PPCAAM) protege quem está sob ameaça grave, providenciando mudança segura de endereço, sigilo e apoio logístico/financeiro. A inclusão é solicitada via Conselho Tutelar, Ministério Público ou Justiça.',
        "fonte": 'Decreto 9.579/2018 (PPCAAM) (https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/decreto/d9579.htm).',
        "validado": True,
    },
]


_EIXOS_META = [
    {"id": 'protecao-resposta-imediata', "numero": 1, "titulo": 'Proteção e Resposta Imediata'},
    {"id": 'conceitos-legislacao', "numero": 2, "titulo": 'Conceitos e Legislação'},
    {"id": 'identificacao-sinais-alerta', "numero": 3, "titulo": 'Identificação e Sinais de Alerta'},
    {"id": 'prevencao-cuidados', "numero": 4, "titulo": 'Prevenção e Cuidados'},
    {"id": 'atendimento-rede-protecao', "numero": 5, "titulo": 'Atendimento, Rede de Proteção e Encaminhamentos'},
]


def _enriquecer(item: dict) -> dict:
    return {**item, "fonte_partes": partes_fonte(item.get("fonte", ""))}


EIXOS_FAQ: list[dict] = [
    {
        **eixo,
        "itens": [
            _enriquecer(i)
            for i in ITENS_FAQ
            if math.ceil(i["n"] / 10) == eixo["numero"]
        ],
    }
    for eixo in _EIXOS_META
]
