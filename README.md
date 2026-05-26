# ISO/IEC 25010 Audit Tool — Java

> Ferramenta automatica de auditoria de qualidade para repositorios Java,
> baseada na norma **ISO/IEC 25010**. Recebe uma URL Git ou caminho local,
> executa analise estatica, dinamica e de confiabilidade, e gera relatorio
> tecnico em **HTML + PDF + JSON**.

---

## Inicio rapido

```bash
# 1. Clonar o repositorio
git clone https://github.com/henriquelazzarino/iso-analyzer.git
cd iso-analyzer

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Baixar Maven + verificar ambiente (so precisa rodar uma vez)
python audit_tool.py setup

# 4. Auditar um repositorio
python audit_tool.py analyze https://github.com/user/projeto
```

---

## Pre-requisitos

| Ferramenta | Versao | Observacao |
|---|---|---|
| **Python** | 3.10+ | deve estar no PATH |
| **Java (JDK)** | 11+ (recomendado 21) | `JAVA_HOME` nao precisa estar configurado |
| **Git** | qualquer | necessario apenas para URLs remotas |
| **Maven** | 3.6+ | baixado automaticamente pelo `setup` |

---

## Configuracao do ambiente

### Passo 1 — Clonar

```bash
git clone https://github.com/henriquelazzarino/iso-analyzer.git
cd iso-analyzer
```

### Passo 2 — Instalar dependencias Python

```bash
pip install -r requirements.txt
```

### Passo 3 — Setup (Maven + verificacao)

```bash
python audit_tool.py setup
```

O comando:
- verifica Java, Git e dependencias Python
- baixa o Maven 3.9.9 automaticamente para `tools/maven/` se nao estiver disponivel
- confirma que tudo esta pronto para rodar

Saida esperada na primeira execucao:

```
=== ISO Analyzer - Setup ===

  [OK] Java: C:\...\jdk-21
  [OK] git: C:\...\git.exe
  [ ] Maven nao encontrado - baixando 3.9.9...
      Baixando de https://dlcdn.apache.org/...
      Extraindo para tools\maven ...
  [OK] Maven instalado em: tools\maven\apache-maven-3.9.9\bin
  [OK] Dependencias Python: requests, reportlab

  Ambiente pronto. Rode: python audit_tool.py analyze <url-ou-pasta>
```

> Se o Maven ja estiver instalado no sistema (`mvn` no PATH),
> o download e pulado automaticamente.

### Passo 4 — Verificar ferramentas detectadas (opcional)

```bash
python audit_tool.py tools
```

---

## Rodando a auditoria

```bash
# URL remota (git clone automatico)
python audit_tool.py analyze https://github.com/user/projeto

# Caminho local
python audit_tool.py analyze C:/repos/meu-projeto

# Pasta de saida personalizada
python audit_tool.py analyze https://github.com/user/projeto --output ./relatorios
```

### Flags

| Flag | Descricao | Padrao |
|---|---|---|
| `--output DIR` | Diretorio de saida | `./audit-output` |
| `--no-dynamic` | Pula benchmark e latencia | — |
| `--no-tests` | Pula testes e cobertura JaCoCo | — |
| `--timeout SEC` | Timeout por fase (segundos) | `300` |
| `--load N,N,...` | Niveis de carga para benchmark | `100,500,1000,5000` |
| `--verbose` | Logs detalhados no terminal | — |

### Exemplos

```bash
# Spring Boot com MySQL — ferramenta substitui por H2 automaticamente
python audit_tool.py analyze https://github.com/Java-Techie-jt/spring-boot-crud-example

# Apenas analise estatica, bem mais rapido
python audit_tool.py analyze https://github.com/user/projeto --no-dynamic --no-tests

# Repositorio local com saida e logs detalhados
python audit_tool.py analyze ./meu-projeto --output ./saida --verbose
```

---

## O que a ferramenta resolve automaticamente

| Situacao | Comportamento automatico |
|---|---|
| Spring Boot com MySQL/PostgreSQL | Substitui datasource por H2 em memoria |
| H2 ausente no `pom.xml` | Adiciona H2 como dependencia `runtime` no clone local |
| Lombok incompativel com JDK 17+ | Override para Lombok 1.18.36 + `--add-opens` via `.mvn/jvm.config` |
| `JAVA_HOME` nao configurado | Detectado automaticamente via `java -XshowSettings:properties` |
| Maven ausente no PATH | Usa Maven local de `tools/maven/` |
| Banco externo inacessivel | Injeta H2 em memoria e continua o benchmark |

---

## Saida gerada

```
audit-output/
    report.html      Dashboard com todas as metricas
    report.pdf       Relatorio executivo para entrega
    metrics.json     Dados brutos (machine-readable)
    audit.log        Log completo da execucao
```

### Veredicto

| Score | Veredicto |
|---|---|
| >= 80 | CONFORME |
| 60 – 79 | CONFORME COM RESSALVAS |
| < 60 | NÃO CONFORME |

### Dimensoes ISO 25010 avaliadas

| Dimensao | Composicao |
|---|---|
| **Manutenibilidade** | Complexidade Ciclomatica 40% + CBO 35% + Duplicacao 25% |
| **Confiabilidade** | Cobertura de linhas JaCoCo 70% + branches 30% |
| **Performance** | Crescimento de latencia entre niveis de carga |

---

## Arquitetura

```
audit/
    core/              Orquestrador + logging
    models/            Dataclasses de metricas e relatorio
    utils/             FS, git, deteccao de ferramentas
    parsers/           Lexer e parser Java manual (regex, sem AST)
    static_analysis/   Complexidade ciclomatica, CBO, duplicacao
    dynamic_analysis/  Descoberta de endpoints, benchmark, latencia
    reliability/       Deteccao de testes + JaCoCo
    executors/         Build runner (Maven/Gradle) + app runner
    reporting/         JSON, HTML, PDF, scorer ISO 25010
```

Cada modulo e **isolado e tolerante a falhas**: se uma fase falhar, as demais
continuam e o relatorio e emitido com os dados disponiveis.

---

## Testes da ferramenta

```bash
python -m unittest discover -s tests -v
```

18 testes unitarios: parser Java, complexidade ciclomatica, CBO, duplicacao,
integracao end-to-end.

---

## Restricoes respeitadas

- Sem SonarQube / PMD / Checkstyle / Spoon / JavaParser
- Parser proprio baseado em regex/tokens (sem AST de terceiros)
- Cross-platform: Windows, Linux, macOS
- Nao trava em projetos quebrados (fallback global em todas as fases)
- Maximo 2 bibliotecas externas: `requests` + `reportlab`

---

## Por que Python?

| Criterio | Justificativa |
|---|---|
| Parser manual | `re` + stdlib — sem dependencia de AST externa |
| Execucao shell | `subprocess` cross-platform nativo |
| Cliente HTTP | `requests` + `urllib` fallback |
| Relatorio PDF | `reportlab` |
| Portabilidade | Linux / macOS / Windows |
| Resiliencia | try/except global + logging estruturado |
