# 🤖 Assistente SQL com Auto-Detecção

Um assistente conversacional inteligente que gera SQL automaticamente a partir de perguntas em português natural, com detecção automática de mudanças no schema e suporte a múltiplos bancos de dados.

## ✨ Features Principais

- 💬 **Chat em Português Natural** - Pergunte sobre seus dados em linguagem natural
- 🧠 **IA Gera SQL Automaticamente** - LLM (Groq) cria queries otimizadas em T-SQL
- 🔄 **Auto-Detecção de Schema** - Detecta automaticamente tabelas, colunas, PKs e FKs
- 🏢 **Suporte a Múltiplos Bancos** - Troca de banco automática com detecção
- 📜 **Histórico de Mudanças** - Registra todas as alterações no schema com timestamp
- 🎯 **Classificação de Intenções** - LLM identifica se é saudação, pergunta genérica ou query SQL
- ⚡ **VectorDB Inteligente** - ChromaDB com embeddings para contexto relevante
- 📊 **Interface Interativa** - Streamlit com métricas em tempo real

## 🚀 Como Funciona

```
Pergunta em Português
        ↓
    LLM Classifica
        ↓
   VectorDB Busca Contexto
        ↓
    IA Gera SQL T-SQL
        ↓
   Executa no Banco
        ↓
   Retorna Dados em Tabela
```

## 📋 Stack Tecnológico

| Componente | Descrição |
|-----------|-----------|
| **Groq** | LLM rápido (Llama 3.3 70B) |
| **LangChain** | Orquestração de IA |
| **ChromaDB** | Vector database para embeddings |
| **Streamlit** | Interface web |
| **SQLAlchemy** | ORM para SQL Server |
| **Sentence Transformers** | Embeddings em português |
| **Pandas** | Processamento de dados |

## 🛠️ Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/assistente-sql-ia.git
cd assistente-sql-ia
```

### 2. Crie um ambiente virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# API Groq
GROQ_API_KEY=sua_chave_groq_aqui

# Conexão SQL Server (customize conforme seu servidor)
# Exemplo:
# SERVER=seu_servidor\MSSQLSERVER01
# DATABASE=VendasDB
# Trusted_Connection=yes
```

**Obtenha sua chave Groq gratuitamente em:** https://console.groq.com

### 5. Execute a aplicação
```bash
streamlit run app.py
```

A aplicação será aberta em `http://localhost:8501`

## 💡 Exemplos de Uso

### Consultas Básicas
```
"Quantos clientes temos?"
"Total de vendas"
"Produto mais caro"
```

### Agregações
```
"Vendas por cliente"
"Média de vendas por mês"
"Top 5 clientes"
```

### Análises
```
"Clientes por estado"
"Produtos por categoria"
"Evolução de vendas mensal"
```

## 🔧 Personalização

### Mudar Conexão de Banco
Edite a função `conectar_banco()` em `app.py`:

```python
@st.cache_resource(show_spinner=False)
def conectar_banco():
    from urllib import parse
    try:
        params = parse.quote_plus(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=seu_servidor\\MSSQLSERVER01;'
            'DATABASE=seu_banco;'
            'Trusted_Connection=yes;'
        )
        return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    except Exception as e:
        st.error(f"❌ Erro ao conectar: {e}")
        return None
```

### Adicionar Descrições de Tabelas
Na função `extrair_schema_completo()`:

```python
descricoes = {
    "Clientes": "Cadastro de clientes",
    "Vendas": "Registro de vendas",
    "Produtos": "Catálogo de produtos",
    "SuaTabela": "Descrição da sua tabela"
}
```

## 📊 Recursos Principais

### Auto-Detecção
- ✅ Detecta novas tabelas automaticamente
- ✅ Detecta mudanças no schema
- ✅ Detecta novos bancos criados
- ✅ Registra histórico com timestamp

### Métricas em Tempo Real
- 🗄️ Número de tabelas
- 📊 Total de consultas executadas
- 💬 Total de mensagens do chat
- 🏢 Banco de dados atual

### Sidebar Inteligente
- Schema detalhado com PKs e FKs
- Histórico de mudanças (últimas 5)
- Botões para limpar chat e atualizar banco

## 🔐 Segurança

- ✅ Chave de API armazenada em `.env`
- ✅ SQL gerado pelo LLM (revisar antes de usar em produção)
- ✅ Sem acesso direto ao código do usuário
- ✅ Dados não são enviados para terceiros (exceto Groq)

## 📝 Limitações

- Requer SQL Server (adaptável para outros bancos)
- Necessário ODBC Driver 17 for SQL Server
- Limite de tokens do LLM (32k para Llama 3.3 70B)
- VectorDB em memória (não persiste entre sessões)

## 🚀 Melhorias Futuras

- [ ] Suporte a PostgreSQL, MySQL
- [ ] Persistência do VectorDB
- [ ] Cache de queries executadas
- [ ] Explicação das queries geradas
- [ ] Export de resultados (CSV, Excel)
- [ ] Suporte a múltiplas conexões simultâneas

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se livre para:
- Reportar bugs
- Sugerir melhorias
- Fazer pull requests

## 📄 Licença

Este projeto está sob licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 👨‍💻 Autor

**Luana Rodrigues** 💜

- LinkedIn: [LinkedIn](https://www.linkedin.com/in/luanac-rodrigues/)


---

**Made with 💜 using Groq + LangChain + ChromaDB**
