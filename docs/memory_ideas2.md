# Память агентов в мультиагентных чат-ботах и виртуальных ассистентах

Память позволяет агентам (LLM-базированным чат-ботам) учитывать предыдущие взаимодействия, а не обрабатывать каждый запрос изолированно. Различают:
- **Краткосрочную память (Short-Term Memory, STM)** — контекст текущей сессии.
- **Долгосрочную память (Long-Term Memory, LTM)** — знания, сохраняемые между сессиями.

## Краткосрочная и долгосрочная память в LangChain

### Краткосрочная память

Модуль `Memory` в LangChain позволяет встроить память в агента или chain. Простейшая реализация — хранение полного диалога в буфере:

```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(return_messages=True)
```

Другие варианты:
- `ConversationBufferWindowMemory` — хранит N последних сообщений.
- `ConversationTokenBufferMemory` — ограничивает по токенам.
- `ConversationSummaryMemory` — хранит краткое резюме диалога:

```python
from langchain.memory import ConversationSummaryMemory

memory = ConversationSummaryMemory(llm=openai, return_messages=True)
memory.save_context({"input": "hi"}, {"output": "whats up"})
print(memory.load_memory_variables({})["history"])
# {'history': [SystemMessage(content='The human greets the AI, to which the AI responds.', ...)]}
```

### Долгосрочная память

Достигается с помощью векторных БД:

```python
import faiss
from langchain_community.vectorstores import FAISS
from langchain_community.docstore import InMemoryDocstore
from langchain.memory import VectorStoreRetrieverMemory

embedding_size = 1536
index = faiss.IndexFlatL2(embedding_size)
vectorstore = FAISS(embedding_function, index, InMemoryDocstore({}), {})
retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
memory = VectorStoreRetrieverMemory(retriever=retriever)

memory.save_context({"input": "My favorite food is pizza"}, {"output": "that's good to know"})
print(memory.load_memory_variables({"prompt": "what food should I eat?"})["history"])
```

Альтернативные классы:
- `EntityMemory` — отслеживание сущностей.
- `ConversationKnowledgeGraphMemory` — построение графа знаний.
- `SummaryBufferMemory` — сочетание буфера и резюме.

Возможны внешние хранилища через `ChatMessageHistory`, например:
- RedisChatMessageHistory
- MongoDBChatMessageHistory
- SQLiteChatMessageHistory

## Краткосрочная и долгосрочная память в LangGraph

LangGraph — библиотека для построения графов агентов и сложных workflow.

### Краткосрочная память

Используется механизм checkpointing (например, `MemorySaver`). История сообщений сохраняется между сессиями в базе (SQLite, PostgreSQL и др.).

### Долгосрочная память

Осуществляется через `Store` (JSON-документы), где каждый элемент имеет namespace и ключ. Пример:

```python
store.put((user_id, "memories"), "a-memory", {"food_preference": "I like pizza"})
```

Поиск воспоминаний:

```python
store.search((user_id, "memories"), query="What does the user like to eat?")
```

LangGraph поддерживает семантический поиск в Store с помощью эмбеддингов. Память делится на:
- **Семантическую** (факты и знания)
- **Эпизодическую** (опыт и события)
- **Процедурную** (навыки и инструкции)

## Архитектуры памяти в мультиагентных системах

1. **Индивидуальная память** — агенты хранят свой контекст.
2. **Общая память** — агенты пишут/читают в общий лог.
3. **Иерархическая память** — сочетание локальной и глобальной памяти.

Примеры:
- Агент-планировщик помнит цели.
- Агент-исполнитель — детали исполнения.

В LangGraph можно настроить `shared_state` с различной степенью обмена сообщениями: полный (`share full history`) или итоговый (`share final result`).

## Retrieval-Augmented Generation (RAG)

Ключевой метод доступа к LTM:
1. Выполняется семантический поиск по памяти.
2. Релевантные фрагменты вставляются в prompt.

Пример в LangChain:
```python
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma

embeddings = OpenAIEmbeddings()
vectordb = Chroma(collection_name="chat_history", embedding_function=embeddings)
vectordb.add_texts(["User: ...\nAssistant: ..."], metadatas=[{"session": "123"}])
docs = vectordb.similarity_search("что пользователь любит есть?", k=1)
```

## Хранение истории взаимодействий

История сообщений, действий и инструментов может храниться:
- В Python-структурах (`ConversationBufferMemory`)
- В БД (`ChatMessageHistory`, `Checkpoint` в LangGraph)

В LangGraph действия агентов могут логироваться через `Command` и `update`. Эпизодическая память может фиксировать, какие задачи решались, как и с каким результатом.

## Векторные базы данных для памяти

Поддерживаемые решения:
- **FAISS** — быстрый локальный поиск.
- **Chroma** — локальная, open-source.
- **Weaviate** — облачная или on-prem, поддержка графов и фильтров.
- **Pinecone** — облачная, с namespace и масштабируемостью.
- **Redis / Milvus / Qdrant / Elasticsearch / pgvector** — возможны.

Пример Pinecone:
```python
import pinecone
pinecone.init(api_key="...", environment="...")
index = pinecone.Index("langchain-memory")

from langchain.vectorstores import Pinecone as PineconeStore
vectorstore = PineconeStore(index, embedding_function, "text")
retriever = vectorstore.as_retriever(search_kwargs={"namespace": user_id, "k": 2})
memory = VectorStoreRetrieverMemory(retriever=retriever)
```

## Сжатие истории и управление контекстом

Методы:
- **Ограничение окна** (`ConversationBufferWindowMemory`).
- **Семантический поиск** (через RAG).
- **Суммирование истории** (`ConversationSummaryMemory`).
- **Chunk-based резюмирование** — деление диалога на блоки и их резюмирование.
- **Knowledge Graph Extraction** (`ConversationKnowledgeGraphMemory`).
- **Оценка важности** — сохранение по значимости (возможна кастомно).
- **Semantic Chunking** — разделение истории по темам.

### Паттерн: Summary + Buffer

1. Хранится `Summary so far` и `Recent messages`.
2. При превышении лимита recent — объединение в новый summary.

### Внешние документы и память

Прочитанные документы можно вынести в векторное хранилище. В диалоге оставить пометку (например, "документ прочитан"), а при необходимости — сделать поиск по документу (RAG).

## Заключение

LangChain и LangGraph предоставляют обширную инфраструктуру для организации памяти агентов:
- STM — краткосрочный буфер или история сообщений
- LTM — через векторные базы, Store, Knowledge Graph
- Поддержка RAG и сжатия истории
- Архитектуры памяти: индивидуальная, общая, иерархическая

Память делает агентов более последовательными, персонализированными и "обучаемыми". Комбинируя буферы, резюме, семантический поиск и Knowledge Graph, можно создавать гибкие и масштабируемые системы памяти.

