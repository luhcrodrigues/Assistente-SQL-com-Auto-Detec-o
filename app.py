import os
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer
import chromadb
import hashlib
import json


# =========================================
# 💜 CONFIGURAÇÃO
# =========================================
st.set_page_config(page_title="Assistente SQL Conversacional", page_icon="😎", layout="wide")
st.title("🤖 Assistente SQL com Auto-Detecção")

# =========================================
# 🔹 SESSION STATE
# =========================================
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "schema_hash_teste" not in st.session_state:
    st.session_state.schema_hash_teste = None
    st.session_state.schema_info = None
    st.session_state.novas_tabelas = set()
    st.session_state.deletadas_tabelas = set()
    st.session_state.total_queries = 0
    st.session_state.historico_mudancas = []
    st.session_state.banco_atual = None


if "cache_classificacoes" not in st.session_state:
    st.session_state.cache_classificacoes = {}


# =========================================
# 🔹 CARREGAR VARIÁVEIS DE AMBIENTE
# =========================================
load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")


if not groq_key:
    st.error("❌ GROQ_API_KEY não encontrada no .env")
    st.info("💡 Certifique-se que o arquivo .env está na raiz com: GROQ_API_KEY=sua_chave")
    st.stop()


# =========================================
# 🔹 CONEXÃO COM BANCO DE DADOS
# =========================================
@st.cache_resource(show_spinner=False)
def conectar_banco():
    """
    Conecta ao banco de dados usando variáveis de ambiente.
    
    Configure no arquivo .env:
    - DB_DRIVER: ODBC Driver 17 for SQL Server
    - DB_SERVER: seu_servidor\INSTANCE
    - DB_DATABASE: seu_banco
    - DB_USER: (opcional, se não usar autenticação Windows)
    - DB_PASSWORD: (opcional, se não usar autenticação Windows)
    """
    from urllib import parse
    try:
        # Ler variáveis de ambiente
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        server = os.getenv("DB_SERVER")
        database = os.getenv("DB_DATABASE")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        
        # Validar variáveis obrigatórias
        if not server or not database:
            st.error("❌ DB_SERVER e DB_DATABASE não configurados no .env")
            st.info("💡 Veja o arquivo .env.example para configurar corretamente")
            return None
        
        # Construir connection string
        if user and password:
            # SQL Authentication
            conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={password}"
        else:
            # Windows Authentication (padrão)
            conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
        
        params = parse.quote_plus(conn_str)
        return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
        
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao banco: {e}")
        st.info("💡 Verifique as configurações no arquivo .env")
        return None


engine = conectar_banco()
if not engine:
    st.stop()


# =========================================
# 🔹 OBTER BANCO ATUAL
# =========================================
def obter_banco_atual():
    """Extrai o nome do banco de dados atual"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT DB_NAME()")
            banco = result.fetchone()[0]
            return banco
    except Exception as e:
        return "Banco Desconhecido"


# =========================================
# 🧠 EXTRAIR SCHEMA COMPLETO COM BANCO
# =========================================
def extrair_schema_completo():
    """Extrai schema COM MÁXIMO DETALHE E BANCO"""
    try:
        inspector = inspect(engine)
        tabelas = inspector.get_table_names()
        banco_nome = obter_banco_atual()
        
        # Descrições customizáveis - adicione suas descrições aqui
        descricoes = {
            # "Tabela": "Descrição da tabela"
            # Exemplo:
            # "Clientes": "Cadastro de clientes com informações de contato",
            # "Vendas": "Registro de vendas vinculadas a clientes",
        }
        
        schema_docs = []
        
        for tabela in tabelas:
            colunas_info = inspector.get_columns(tabela)
            pks = inspector.get_pk_constraint(tabela)
            fks = inspector.get_foreign_keys(tabela)
            
            pk_cols = pks.get('constrained_columns', [])
            
            detalhes_colunas = []
            for col in colunas_info:
                tipo = str(col['type'])
                nulo = "nullable" if col['nullable'] else "NOT NULL"
                extra = ", PK" if col['name'] in pk_cols else ""
                detalhes_colunas.append(f"{col['name']} ({tipo}, {nulo}{extra})")
            
            colunas_str = ", ".join(detalhes_colunas)
            
            fk_info = ""
            if fks:
                fk_desc = []
                for fk in fks:
                    const = ', '.join(fk['constrained_columns'])
                    ref = f"{fk['referred_table']}.{', '.join(fk['referred_columns'])}"
                    fk_desc.append(f"{const} → {ref}")
                fk_info = f"\n  Relações: {' | '.join(fk_desc)}"
            
            descricao = descricoes.get(tabela, "Tabela de dados")
            doc_text = f"[{banco_nome}] Tabela {tabela} ({descricao}):\n  {colunas_str}{fk_info}"
            
            schema_docs.append({
                "text": doc_text,
                "metadata": {"tabela": tabela, "tipo": "schema", "banco": banco_nome}
            })
        
        return schema_docs, banco_nome
        
    except Exception as e:
        st.error(f"❌ Erro ao extrair schema: {e}")
        return [], "Desconhecido"


# =========================================
# 🔐 HASH & VERIFICAÇÃO COM BANCO
# =========================================
def gerar_hash_schema():
    try:
        inspector = inspect(engine)
        tabelas = sorted(inspector.get_table_names())
        banco_nome = obter_banco_atual()
        schema_info = {}
        
        for tabela in tabelas:
            colunas = sorted([col['name'] for col in inspector.get_columns(tabela)])
            schema_info[tabela] = colunas
        
        schema_json = json.dumps(schema_info, sort_keys=True)
        hash_atual = hashlib.md5(schema_json.encode()).hexdigest()
        return hash_atual, schema_info, banco_nome
    except Exception as e:
        return None, None, None


def verificar_mudancas():
    hash_novo, schema_novo, banco_novo = gerar_hash_schema()
    
    if hash_novo is None:
        return False, None, None, None, None, None
    
    if st.session_state.schema_hash_teste is None:
        st.session_state.schema_hash_teste = hash_novo
        st.session_state.schema_info = schema_novo
        st.session_state.banco_atual = banco_novo
        return False, None, hash_novo, schema_novo, banco_novo, None
    
    hash_anterior = st.session_state.schema_hash_teste
    banco_anterior = st.session_state.banco_atual
    
    # Verificar se mudou de banco
    if banco_novo != banco_anterior:
        st.session_state.historico_mudancas.append({
            "timestamp": datetime.now().isoformat(),
            "tipo": "banco_novo",
            "banco_anterior": banco_anterior,
            "banco_novo": banco_novo
        })
        st.session_state.banco_atual = banco_novo
        st.session_state.schema_hash_teste = hash_novo
        st.session_state.schema_info = schema_novo
        return True, hash_anterior, hash_novo, schema_novo, banco_novo, "BANCO_NOVO"
    
    # Verificar mudanças no schema
    if hash_novo != hash_anterior:
        tabelas_anterior = set(st.session_state.schema_info.keys())
        tabelas_nova = set(schema_novo.keys())
        
        novas = tabelas_nova - tabelas_anterior
        deletadas = tabelas_anterior - tabelas_nova
        
        st.session_state.historico_mudancas.append({
            "timestamp": datetime.now().isoformat(),
            "tipo": "schema",
            "banco": banco_novo,
            "novas": list(novas),
            "deletadas": list(deletadas)
        })
        
        st.session_state.schema_hash_teste = hash_novo
        st.session_state.schema_info = schema_novo
        st.session_state.novas_tabelas = novas
        st.session_state.deletadas_tabelas = deletadas
        
        return True, hash_anterior, hash_novo, schema_novo, banco_novo, "SCHEMA_MUDOU"
    
    return False, hash_anterior, hash_novo, schema_novo, banco_novo, None


# =========================================
# 🔹 VECTORDB (SEM SPINNER)
# =========================================
@st.cache_resource(show_spinner=False)
def criar_vectordb_teste():
    model = SentenceTransformer("neuralmind/bert-base-portuguese-cased")
    client = chromadb.Client()
    coll = client.create_collection(f"chat_sql_{datetime.now().timestamp()}")
    
    docs_base = [
        {"text": "SQL Server: COUNT(*), SUM(), AVG(), YEAR(), MONTH(), TOP N", "metadata": {"tipo": "funcoes"}},
        {"text": "JOIN: FROM Clientes c JOIN Vendas v ON c.id = v.cliente_id", "metadata": {"tipo": "joins"}},
        {"text": "GROUP BY obrigatório com agregações. Ex: SELECT estado, COUNT(*) FROM Clientes GROUP BY estado", "metadata": {"tipo": "sintaxe"}},
    ]
    
    docs_schema, banco_nome = extrair_schema_completo()
    todos_docs = docs_base + docs_schema
    
    for i, d in enumerate(todos_docs):
        emb = model.encode([d["text"]]).tolist()
        coll.add(documents=[d["text"]], embeddings=emb, metadatas=[d["metadata"]], ids=[f"doc_{i}"])
    
    return coll, model, todos_docs, banco_nome


# =========================================
# 🚨 VERIFICAR MUDANÇAS
# =========================================
mudou, hash_ant, hash_novo, schema, banco_atual, tipo_mudanca = verificar_mudancas()

if mudou:
    with st.expander("🚨 MUDANÇA DETECTADA!", expanded=True):
        
        if tipo_mudanca == "BANCO_NOVO":
            st.error(f"🔄 **NOVO BANCO DETECTADO!**")
            st.code(f"Banco Anterior: {st.session_state.historico_mudancas[-1]['banco_anterior']}\nBanco Novo: {banco_atual}", language="text")
            st.info(f"✅ Sistema recarregado para o banco: **{banco_atual}**")
        
        elif tipo_mudanca == "SCHEMA_MUDOU":
            col1, col2 = st.columns(2)
            with col1:
                st.warning(f"✅ Schema Atualizado em **{banco_atual}**!")
                st.code(f"Anterior: {hash_ant[:12]}...\nNovo: {hash_novo[:12]}...", language="text")
            with col2:
                if st.session_state.novas_tabelas:
                    st.success(f"➕ **Novas:** {', '.join(st.session_state.novas_tabelas)}")
                if st.session_state.deletadas_tabelas:
                    st.error(f"➖ **Removidas:** {', '.join(st.session_state.deletadas_tabelas)}")
            st.info("🔄 Sistema recarregado! Faça perguntas sobre as novas tabelas.")
    
    st.cache_resource.clear()


collection, embedder, docs_info, banco_nome = criar_vectordb_teste()


# =========================================
# 📊 MÉTRICAS
# =========================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    num_tabelas = len([d for d in docs_info if d["metadata"].get("tipo") == "schema"])
    st.metric("🗄️ Tabelas", num_tabelas)
with col2:
    st.metric("📊 Consultas", st.session_state.total_queries)
with col3:
    st.metric("💬 Mensagens", len(st.session_state.messages))
with col4:
    st.metric("🏢 Banco", banco_nome)

st.markdown("---")


# =========================================
# 📊 SIDEBAR
# =========================================
with st.sidebar:
    st.markdown(f"### 📋 Schema - {banco_nome}")
    
    tabelas_detectadas = [d for d in docs_info if d["metadata"].get("tipo") == "schema"]
    if tabelas_detectadas:
        st.success(f"✅ {len(tabelas_detectadas)} tabelas")
        for doc in tabelas_detectadas:
            with st.expander(f"📊 {doc['metadata']['tabela']}"):
                st.text(doc['text'])
    
    st.divider()
    
    if st.session_state.historico_mudancas:
        st.markdown("### 📜 Histórico de Mudanças")
        for h in reversed(st.session_state.historico_mudancas[-5:]):
            if h.get("tipo") == "banco_novo":
                with st.expander(f"🔄 {h['timestamp'][:19]} - BANCO"):
                    st.error(f"De: {h['banco_anterior']}")
                    st.success(f"Para: {h['banco_novo']}")
            else:
                with st.expander(f"🕐 {h['timestamp'][:19]} - {h.get('banco', 'N/A')}"):
                    if h.get('novas'):
                        st.success(f"➕ {', '.join(h['novas'])}")
                    if h.get('deletadas'):
                        st.error(f"➖ {', '.join(h['deletadas'])}")
    
    st.divider()
    
    if st.button("🗑️ Limpar Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 Atualizar Banco", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()


# =========================================
# 🧠 CLASSIFICAR INTENÇÃO (LLM)
# =========================================
def classificar_intencao(pergunta, tabelas_conhecidas):
    """LLM decide se deve executar SQL ou não"""
    
    pergunta_norm = pergunta.lower().strip()
    if pergunta_norm in st.session_state.cache_classificacoes:
        return st.session_state.cache_classificacoes[pergunta_norm]
    
    tabelas_str = ", ".join(tabelas_conhecidas)
    
    prompt = f"""Você é um classificador de intenções para assistente SQL.

TABELAS DISPONÍVEIS: {tabelas_str}

PERGUNTA DO USUÁRIO: "{pergunta}"

Classifique em UMA categoria:

1. SAUDACAO - Cumprimentos (oi, olá, bom dia, boa noite)
2. GENERICA - Perguntas sobre o sistema ("como funciona?", "o que você faz?")
3. QUERY_SQL - Pergunta que requer consulta SQL
4. IRRELEVANTE - Texto sem sentido

REGRAS:
- Se menciona dados/tabelas/análises → QUERY_SQL
- Se pergunta sobre sistema → GENERICA
- Se é cumprimento → SAUDACAO
- Se não faz sentido → IRRELEVANTE

Responda APENAS a categoria (uma palavra).

CATEGORIA:"""
    
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, api_key=groq_key)
        resposta = llm.invoke(prompt)
        categoria = resposta.content.strip().upper()
        
        categorias_validas = ["SAUDACAO", "GENERICA", "QUERY_SQL", "IRRELEVANTE"]
        if categoria not in categorias_validas:
            categoria = "QUERY_SQL"
        
        st.session_state.cache_classificacoes[pergunta_norm] = categoria
        
        return categoria
        
    except Exception as e:
        return "QUERY_SQL"


# =========================================
# 🤖 GERAR SQL
# =========================================
def gerar_sql_teste(pergunta, contexto):
    mensagem_extra = ""
    if st.session_state.novas_tabelas:
        mensagem_extra = f"\n\n🆕 NOVAS TABELAS: {', '.join(st.session_state.novas_tabelas)}"
    
    prompt = f"""Você é especialista em SQL Server (T-SQL).

BANCO: {banco_nome}

SCHEMA DO BANCO:
{contexto}{mensagem_extra}

REGRAS OBRIGATÓRIAS:
1. SQL Server: use TOP N (NUNCA use LIMIT)
2. Não use SELECT * — especifique as colunas
3. Use YEAR(coluna), MONTH(coluna) para datas
4. GROUP BY obrigatório com agregações
5. Use relações FK do schema para JOINs

PERGUNTA: {pergunta}

Retorne APENAS o SQL puro (sem markdown).

SQL:
"""
    
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, api_key=groq_key)
        resposta = llm.invoke(prompt)
        
        sql = resposta.content.strip()
        
        # Limpar markdown
        if sql.startswith("```"):
            sql = sql.replace("```sql", "").replace("```", "")
        
        # Limpar caracteres invisíveis
        sql = sql.replace("\u200b", "").replace("\ufeff", "")
        
        return sql.strip()
        
    except Exception as e:
        st.error(f"❌ Erro ao gerar SQL: {e}")
        return None


# =========================================
# 💬 CHAT CONVERSACIONAL
# =========================================
st.markdown("### 💬 Chat com Assistente SQL")


# Histórico
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(f"**Você:** {message['content']}")
        else:
            st.markdown(message['content'])
            if "sql" in message:
                st.code(message["sql"], language="sql")
            if "dataframe" in message:
                st.dataframe(message["dataframe"], use_container_width=True)


# Input
if prompt := st.chat_input("💬 Faça sua pergunta sobre o banco de dados..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(f"**Você:** {prompt}")
    
    # =========================================
    # 🧠 LLM CLASSIFICA
    # =========================================
    tabelas = [d["metadata"]["tabela"] for d in docs_info if d["metadata"].get("tipo") == "schema"]
    
    categoria = classificar_intencao(prompt, tabelas)
    
    # =========================================
    # 📋 RESPONDER POR CATEGORIA
    # =========================================
    with st.chat_message("assistant"):
        
        if categoria == "SAUDACAO":
            resposta = """Olá! 👋 Como posso ajudar com consultas ao banco?

💡 **Experimente:**
- Quantos clientes temos?
- Top 5 produtos mais caros
- Total de vendas por cliente"""
            
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
        
        elif categoria == "GENERICA":
            resposta = f"""Sou um assistente SQL com IA! 🤖
                
**Banco Atual:** {banco_nome}
**Tabelas disponíveis:** {', '.join(tabelas)}

**Como funciono:**
1. Você pergunta em português
2. Gero SQL automaticamente
3. Executo no banco
4. Retorno dados em tabela

**Exemplos:**
- "Quantos clientes temos?"
- "Produtos mais caros"
- "Vendas por cliente"
"""
            
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
        
        elif categoria == "IRRELEVANTE":
            resposta = "🤔 Não entendi. Posso ajudar com consultas sobre os dados. O que gostaria de saber?"
            
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
        
        else:  # QUERY_SQL
            with st.status("⚡ Processando consulta...", expanded=False) as status:
                
                # Buscar contexto
                query_emb = embedder.encode([prompt]).tolist()
                results = collection.query(query_embeddings=query_emb, n_results=7)
                docs_list = results["documents"][0] if results["documents"] else []
                contexto = "\n\n".join(docs_list)
                
                # Gerar SQL
                try:
                    sql = gerar_sql_teste(prompt, contexto)
                    
                    if sql is None:
                        status.update(label="❌ Erro ao gerar SQL", state="error")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "❌ Não consegui gerar o SQL para sua pergunta."
                        })
                        st.stop()
                    
                    st.code(sql, language="sql")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao gerar SQL: {e}")
                    status.update(label="❌ Erro", state="error")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"❌ Erro ao gerar SQL: {e}"
                    })
                    st.stop()
                
                # Executar
                try:
                    df = pd.read_sql(sql, engine)
                    st.session_state.total_queries += 1
                    
                    resultado_msg = f"✅ **{len(df)} registros retornados**"
                    st.success(resultado_msg)
                    st.dataframe(df, use_container_width=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resultado_msg,
                        "sql": sql,
                        "dataframe": df
                    })
                    
                    status.update(label="✅ Concluído!", state="complete")
                    
                except Exception as e:
                    erro_msg = f"❌ Erro ao executar: {str(e)[:300]}"
                    st.error(erro_msg)
                    st.info("💡 SQL pode estar incorreto")
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": erro_msg,
                        "sql": sql
                    })
                    
                    status.update(label="❌ Erro na execução", state="error")


# =========================================
# 📚 INFORMAÇÕES
# =========================================
st.markdown("---")


col1, col2 = st.columns(2)


with col1:
    with st.expander("💡 Exemplos de Perguntas"):
        st.markdown("""
        **Consultas Básicas:**
        - "Quantos clientes temos?"
        - "Total de vendas"
        - "Produto mais caro"
        
        **Agregações:**
        - "Vendas por cliente"
        - "Média de vendas por mês"
        - "Top 5 clientes"
        
        **Análises:**
        - "Clientes por estado"
        - "Produtos por categoria"
        """)


with col2:
    with st.expander("🎬 Como Funciona"):
        st.markdown(f"""
        **Fluxo:**
        
        1. **LLM classifica** → Saudação ou query SQL?
        2. **Busca contexto** → VectorDB com schema
        3. **IA gera SQL** → T-SQL otimizado para {banco_nome}
        4. **Executa** → No banco real
        5. **Retorna dados** → Tabela interativa
        
        **Auto-Detecção:**
        - Schema via MD5 hash
        - Novas tabelas automáticas
        - **Detecção de novo banco!**
        - Zero configuração!
        """)


st.markdown("<p style='text-align:center;color:#888;'>🤖 Feito por Luana Rodrigues | Groq + LangChain + ChromaDB</p>", unsafe_allow_html=True)