"""Recursos institucionais da seção Links Úteis (espelha prototype_02/src/data/recursos.ts)."""

from __future__ import annotations

CATEGORIAS_RECURSOS: list[dict] = [
    {
        "id": "denuncia-e-protecao",
        "numero": "1",
        "titulo": "Denúncia e Proteção",
        "resumo": (
            "Canais oficiais de denúncia e serviços de proteção a crianças e "
            "adolescentes em situação de violação de direitos."
        ),
        "itens": [
            {
                "titulo": "Disque Direitos Humanos — Disque 100",
                "descricao": (
                    "Canal nacional gratuito e anônimo para denúncias de violações "
                    "de direitos humanos, incluindo violência contra crianças e "
                    "adolescentes. Funciona 24 horas, todos os dias."
                ),
                "url": "https://www.gov.br/mdh/pt-br/ondh/disque-100",
                "orgao": "MDHC",
            },
            {
                "titulo": "Dados Abertos do Disque 100",
                "descricao": (
                    "Microdados das denúncias recebidas pelo Disque 100, em formato "
                    "CSV, com registros históricos desde 2011."
                ),
                "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos",
                "orgao": "MDHC",
            },
            {
                "titulo": "Acesso ao SIPIA — Conselho Tutelar (SIPIA-CT)",
                "descricao": (
                    "Serviço oficial de acesso ao sistema SIPIA-CT, já utilizado "
                    "como fonte de dados na Plataforma Aurora, para consulta e "
                    "registro de demandas de violação de direitos pelos Conselhos Tutelares."
                ),
                "url": (
                    "https://www.gov.br/pt-br/servicos/solicitar-acesso-ao-sistema-de-"
                    "informacao-para-a-infancia-e-adolescencia-sipia-conselho-tutelar"
                ),
                "orgao": "MDHC",
            },
            {
                "titulo": "Enfrentamento ao Tráfico de Pessoas",
                "descricao": (
                    "Página institucional com canais de denúncia, sinais de alerta "
                    "e orientações sobre tráfico de pessoas."
                ),
                "url": "https://www.gov.br/mj/pt-br/assuntos/sua-protecao/trafico-de-pessoas",
                "orgao": "MJSP",
            },
        ],
    },
    {
        "id": "dados-e-evidencias",
        "numero": "2",
        "titulo": "Dados e Evidências",
        "resumo": (
            "Fontes, estudos e repositórios que ampliam o acesso a dados "
            "complementares aos painéis analíticos da plataforma."
        ),
        "itens": [
            {
                "titulo": "VIVA/SINAN — Vigilância de Violência Interpessoal",
                "descricao": (
                    "Sistema de notificação de violência interpessoal e autoprovocada "
                    "(base SINAN, já citada na Plataforma Aurora), com instrutivos e "
                    "normas técnicas de preenchimento."
                ),
                "url": (
                    "https://www.gov.br/saude/pt-br/composicao/svsa/"
                    "vigilancia-de-violencias-e-acidentes"
                ),
                "orgao": "Ministério da Saúde",
            },
            {
                "titulo": "Atlas da Violência",
                "descricao": (
                    "Séries históricas, mapas e planilhas sobre violência no Brasil, "
                    "incluindo recortes por idade, raça e sexo, complementares aos "
                    "indicadores do Dashboard Aurora."
                ),
                "url": "https://www.ipea.gov.br/atlasviolencia/",
                "orgao": "IPEA / FBSP",
            },
            {
                "titulo": "IBGE Cidades",
                "descricao": (
                    "Painel com dados populacionais e socioeconômicos por município "
                    "e Unidade da Federação, base de referência para a seção Dados Demográficos."
                ),
                "url": "https://cidades.ibge.gov.br/",
                "orgao": "IBGE",
            },
        ],
    },
    {
        "id": "exploracao-sexual-e-trafico",
        "numero": "3",
        "titulo": "Exploração Sexual e Tráfico de Pessoas",
        "resumo": (
            "Órgãos, redes e organizações dedicados à prevenção e ao enfrentamento "
            "da exploração sexual e do tráfico de crianças e adolescentes."
        ),
        "itens": [
            {
                "titulo": "Enfrentamento ao Tráfico de Pessoas (MJSP)",
                "descricao": (
                    "Política nacional de enfrentamento ao tráfico de pessoas, com "
                    "orientações, sinais de alerta e canais de denúncia."
                ),
                "url": "https://www.gov.br/mj/pt-br/assuntos/sua-protecao/trafico-de-pessoas",
                "orgao": "MJSP",
            },
            {
                "titulo": "Comitês Estaduais de Enfrentamento ao Tráfico — CONATRAP",
                "descricao": (
                    "Relação dos comitês estaduais responsáveis pela articulação "
                    "local da política de enfrentamento ao tráfico de pessoas."
                ),
                "url": "https://www.gov.br/mj/pt-br/assuntos/sua-protecao/trafico-de-pessoas",
                "orgao": "MJSP",
            },
            {
                "titulo": "Childhood Brasil (Instituto WCF Brasil)",
                "descricao": (
                    "Organização da sociedade civil dedicada à prevenção e ao "
                    "enfrentamento do abuso e da exploração sexual de crianças e "
                    "adolescentes, com materiais educativos e técnicos."
                ),
                "url": "https://www.childhood.org.br/",
                "orgao": "Sociedade civil",
            },
            {
                "titulo": "Rede ECPAT Brasil",
                "descricao": (
                    "Coalizão de organizações da sociedade civil voltada à eliminação "
                    "da exploração sexual de crianças e adolescentes."
                ),
                "url": "http://ecpatbrasil.org.br/",
                "orgao": "Sociedade civil",
            },
        ],
    },
    {
        "id": "legislacao",
        "numero": "4",
        "titulo": "Legislação",
        "resumo": (
            "Marco normativo nacional de proteção de crianças e adolescentes e de "
            "enfrentamento ao tráfico de pessoas, com acesso aos textos oficiais."
        ),
        "itens": [
            {
                "titulo": "Lei nº 8.069/1990 — Estatuto da Criança e do Adolescente (ECA)",
                "descricao": (
                    "Texto compilado oficial do ECA, marco legal nacional de proteção "
                    "integral à criança e ao adolescente."
                ),
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
                "orgao": "Presidência da República",
            },
            {
                "titulo": "Lei nº 13.344/2016 — Enfrentamento ao Tráfico de Pessoas",
                "descricao": (
                    "Dispõe sobre prevenção e repressão ao tráfico interno e "
                    "internacional de pessoas e sobre medidas de atenção às vítimas."
                ),
                "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13344.htm",
                "orgao": "Presidência da República",
            },
            {
                "titulo": "Lei nº 13.431/2017 — Escuta Protegida",
                "descricao": (
                    "Estabelece o sistema de garantia de direitos da criança e do "
                    "adolescente vítima ou testemunha de violência."
                ),
                "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm",
                "orgao": "Presidência da República",
            },
            {
                "titulo": "Lei nº 14.344/2022 — Lei Henry Borel",
                "descricao": (
                    "Cria mecanismos para a prevenção e o enfrentamento da violência "
                    "doméstica e familiar contra a criança e o adolescente."
                ),
                "url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14344.htm",
                "orgao": "Presidência da República",
            },
            {
                "titulo": "Decreto nº 9.579/2018",
                "descricao": (
                    "Consolida atos normativos sobre criança, adolescente e "
                    "aprendizagem profissional, incluindo o funcionamento do CONANDA."
                ),
                "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/decreto/d9579.htm",
                "orgao": "Presidência da República",
            },
        ],
    },
    {
        "id": "rede-institucional",
        "numero": "5",
        "titulo": "Rede Institucional de Enfrentamento ao Tráfico de Pessoas",
        "resumo": (
            "Órgãos e estruturas que atuam na identificação, no atendimento e na "
            "proteção de crianças e adolescentes vítimas de tráfico de pessoas, "
            "conforme a matriz institucional da Plataforma Aurora."
        ),
        "itens": [
            {
                "titulo": "Defensoria Pública da União — DPU",
                "descricao": (
                    "Assistência jurídica gratuita e defesa de direitos. No "
                    "enfrentamento ao tráfico de pessoas, atua pelo GT de Assistência "
                    "e Proteção à Vítima de Tráfico de Pessoas (GTTP)."
                ),
                "url": "https://www.dpu.def.br/",
                "orgao": "DPU",
            },
            {
                "titulo": "Ministério Público Federal — MPF",
                "descricao": (
                    "Atuação judicial e extrajudicial, com estrutura especializada "
                    "de identificação, prevenção e repressão ao tráfico internacional de pessoas."
                ),
                "url": "https://www.mpf.mp.br/",
                "orgao": "MPF",
            },
            {
                "titulo": "Ministério Público do Trabalho — MPT",
                "descricao": (
                    "Proteção de direitos trabalhistas e enfrentamento ao trabalho "
                    "escravo e ao tráfico de pessoas, por meio da CONAETE."
                ),
                "url": "https://mpt.mp.br/",
                "orgao": "MPT",
            },
            {
                "titulo": "Conselho Nacional de Justiça — CNJ (DataJud)",
                "descricao": (
                    "API pública do DataJud, base nacional de dados do Poder "
                    "Judiciário, útil para pesquisa e evidências sobre processos relacionados."
                ),
                "url": "https://www.cnj.jus.br/sistemas/datajud/api-publica/",
                "orgao": "CNJ",
            },
            {
                "titulo": "Polícia Rodoviária Federal — PRF",
                "descricao": (
                    "Identificação de situações suspeitas em rodovias federais e "
                    "repressão a crimes relacionados. Em urgências, ligue 191."
                ),
                "url": "https://www.gov.br/prf/pt-br",
                "orgao": "PRF",
            },
            {
                "titulo": "Polícia Federal — PF",
                "descricao": (
                    "Identificação, investigação e repressão ao tráfico de pessoas, "
                    "especialmente em situações de competência federal e transnacional."
                ),
                "url": "https://www.gov.br/pf/pt-br/",
                "orgao": "PF",
            },
            {
                "titulo": "MJSP — Enfrentamento ao Tráfico de Pessoas (DEMIG/CGETP)",
                "descricao": (
                    "Coordenação da Política Nacional de Enfrentamento ao Tráfico "
                    "de Pessoas: prevenção, proteção e assistência às vítimas, "
                    "repressão e monitoramento do Plano Nacional."
                ),
                "url": "https://www.gov.br/mj/pt-br/assuntos/sua-protecao/trafico-de-pessoas",
                "orgao": "MJSP",
            },
            {
                "titulo": "CONATRAP — Comitê Nacional de Enfrentamento ao Tráfico de Pessoas",
                "descricao": (
                    "Instância nacional de articulação da política de enfrentamento "
                    "ao tráfico de pessoas e dos comitês estaduais."
                ),
                "url": (
                    "https://www.gov.br/mj/pt-br/assuntos/sua-protecao/"
                    "trafico-de-pessoas/conatrap"
                ),
                "orgao": "MJSP",
            },
            {
                "titulo": (
                    "MDHC — Secretaria Nacional dos Direitos da Criança e do "
                    "Adolescente (SNDCA)"
                ),
                "descricao": (
                    "Coordenação das políticas nacionais de proteção de crianças e "
                    "adolescentes, incluindo o Disque 100 e a rede de garantia de direitos."
                ),
                "url": "https://www.gov.br/mdh/pt-br/navegue-por-temas/crianca-e-adolescente",
                "orgao": "MDHC",
            },
            {
                "titulo": "MDS — Assistência Social / SUAS",
                "descricao": (
                    "Coordenação da política nacional de assistência social e proteção "
                    "socioassistencial, com atendimento pelos CRAS e CREAS dos municípios."
                ),
                "url": "https://aplicacoes.mds.gov.br/sagi/snas/inicio.html",
                "orgao": "MDS",
            },
            {
                "titulo": "Ministério do Trabalho e Emprego — Inspeção do Trabalho",
                "descricao": (
                    "Auditoria-fiscal do trabalho para identificação e repressão à "
                    "exploração laboral e ao trabalho infantil."
                ),
                "url": "https://www.gov.br/trabalho-e-emprego/pt-br",
                "orgao": "MTE",
            },
            {
                "titulo": "Ministério da Educação — Dados Abertos",
                "descricao": (
                    "Dados abertos da rede de educação, úteis para ações de prevenção "
                    "e identificação no ambiente escolar."
                ),
                "url": "https://www.gov.br/mec/pt-br/acesso-a-informacao/dados-abertos",
                "orgao": "MEC",
            },
            {
                "titulo": "Ministério das Relações Exteriores — Rede Consular",
                "descricao": (
                    "Apoio consular a vítimas brasileiras de tráfico de pessoas no "
                    "exterior e cooperação internacional."
                ),
                "url": "https://www.gov.br/mre/pt-br",
                "orgao": "MRE",
            },
            {
                "titulo": "Advocacia-Geral da União — AGU",
                "descricao": (
                    "Representação judicial e consultoria jurídica da União nas "
                    "ações de enfrentamento ao tráfico de pessoas."
                ),
                "url": "https://www.gov.br/agu/pt-br",
                "orgao": "AGU",
            },
        ],
    },
]
