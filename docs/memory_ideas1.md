# Реализация памяти для мультиагентных систем

## Содержание
1. [Введение](#введение)
2. [Проблема контекстного окна](#проблема-контекстного-окна)
3. [Подходы к реализации памяти](#подходы-к-реализации-памяти)
   - [Буферная память](#буферная-память)
   - [Суммаризация](#суммаризация)
   - [Векторные базы данных](#векторные-базы-данных)
   - [Retrieval Augmented Generation (RAG)](#retrieval-augmented-generation-rag)
   - [Иерархическая память](#иерархическая-память)
4. [Реализации в LangChain](#реализации-в-langchain)
   - [ConversationBufferMemory](#conversationbuffermemory)
   - [ConversationSummaryMemory](#conversationsummarymemory)
   - [VectorStoreRetrieverMemory](#vectorstoreretrievermemory)
   - [Сохранение и загрузка памяти](#сохранение-и-загрузка-памяти)
5. [Реализации в LangGraph](#реализации-в-langgraph)
   - [Долгосрочная память в LangGraph](#долгосрочная-память-в-langgraph)
   - [Интеграция с RAG](#интеграция-с-rag)
   - [Управление состоянием](#управление-состоянием)
6. [Примеры кода](#примеры-кода)
   - [Базовая реализация памяти](#базовая-реализация-памяти)
   - [Суммаризация истории](#суммаризация-истории)
   - [RAG-память](#rag-память)
   - [Управление контекстным окном](#управление-контекстным-окном)
   - [Иерархическая память](#иерархическая-память-1)
7. [Рекомендации и лучшие практики](#рекомендации-и-лучшие-практики)
8. [Заключение](#заключение)
9. [Ссылки](#ссылки)

## Введение

Мультиагентные системы на основе больших языковых моделей (LLM) сталкиваются с фундаментальной проблемой: как обеспечить агентам доступ к прошлым взаимодействиям и важной информации без переполнения контекстного окна. Эта проблема особенно актуальна для длительных диалогов или сложных задач, требующих сохранения контекста.

В данном отчете рассматриваются различные подходы к реализации памяти для мультиагентных систем, с особым фокусом на библиотеки LangChain и LangGraph. Мы исследуем как простые решения, так и более сложные архитектуры, включая применение Retrieval Augmented Generation (RAG) и иерархических систем памяти.

## Проблема контекстного окна

Контекстное окно LLM ограничено определенным количеством токенов (например, 4K, 8K, 16K или 32K токенов в зависимости от модели). При длительных взаимодействиях история диалога может быстро заполнить это окно, что приводит к следующим проблемам:

1. **Потеря информации**: Модель не может учитывать информацию, выходящую за пределы контекстного окна.
2. **Увеличение стоимости**: Больший размер контекста увеличивает стоимость запросов к API.
3. **Снижение производительности**: Обработка больших контекстов требует больше времени и ресурсов.

Эффективная система памяти должна решать эти проблемы, обеспечивая доступ к релевантной информации без необходимости включать всю историю взаимодействий в каждый запрос.

## Подходы к реализации памяти

### Буферная память

Самый простой подход — хранение полной истории взаимодействий в буфере и включение её в каждый запрос. Этот метод эффективен для коротких диалогов, но быстро достигает ограничений при длительных взаимодействиях.

**Преимущества**:
- Простота реализации
- Полное сохранение контекста

**Недостатки**:
- Быстрое заполнение контекстного окна
- Неэффективное использование токенов

### Суммаризация

Этот подход использует LLM для создания сжатых резюме предыдущих взаимодействий. Вместо полной истории в контекст включается только её суммаризация.

**Преимущества**:
- Значительное сокращение размера контекста
- Сохранение ключевой информации

**Недостатки**:
- Потенциальная потеря деталей
- Дополнительные затраты на генерацию суммаризаций

### Векторные базы данных

Этот метод предполагает хранение истории взаимодействий в векторной базе данных и извлечение только релевантных фрагментов при необходимости.

**Преимущества**:
- Эффективное использование контекстного окна
- Масштабируемость для длительных взаимодействий

**Недостатки**:
- Сложность реализации
- Зависимость от качества векторных представлений

### Retrieval Augmented Generation (RAG)

RAG объединяет генеративные возможности LLM с извлечением информации из внешних источников. В контексте памяти агентов, RAG позволяет хранить историю взаимодействий во внешнем хранилище и извлекать только релевантные части при формировании ответа.

**Преимущества**:
- Высокая масштабируемость
- Эффективное использование контекстного окна
- Возможность интеграции с другими источниками знаний

**Недостатки**:
- Сложность настройки и оптимизации
- Зависимость от качества поиска

### Иерархическая память

Этот подход сочетает несколько уровней памяти с различными характеристиками:
- **Краткосрочная память**: Последние несколько взаимодействий
- **Среднесрочная память**: Суммаризации предыдущих частей диалога
- **Долгосрочная память**: Ключевая информация, хранящаяся в векторной базе данных

**Преимущества**:
- Оптимальный баланс между детализацией и эффективностью
- Гибкость в управлении различными типами информации

**Недостатки**:
- Высокая сложность реализации
- Необходимость тонкой настройки для конкретных сценариев

## Реализации в LangChain

LangChain предоставляет несколько готовых реализаций памяти, которые можно использовать в мультиагентных системах.

### ConversationBufferMemory

Самая простая форма памяти в LangChain, которая хранит все сообщения в буфере и включает их в каждый запрос.

```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.llms import OpenAI

memory = ConversationBufferMemory()
conversation = ConversationChain(
    llm=OpenAI(),
    memory=memory,
    verbose=True
)

conversation.predict(input="Привет! Меня зовут Алиса.")
conversation.predict(input="Как меня зовут?")
```

### ConversationSummaryMemory

Эта реализация использует LLM для суммаризации предыдущих взаимодействий, что позволяет эффективнее использовать контекстное окно.

```python
from langchain.memory import ConversationSummaryMemory
from langchain.chains import ConversationChain
from langchain.llms import OpenAI

memory = ConversationSummaryMemory(llm=OpenAI())
conversation = ConversationChain(
    llm=OpenAI(),
    memory=memory,
    verbose=True
)
```

### VectorStoreRetrieverMemory

Эта реализация использует векторное хранилище для сохранения истории и извлечения релевантных фрагментов при необходимости.

```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma

embeddings = OpenAIEmbeddings()
vectorstore = Chroma(embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs=dict(k=5))
memory = VectorStoreRetrieverMemory(retriever=retriever)
```

### Сохранение и загрузка памяти

LangChain также предоставляет механизмы для сохранения и загрузки памяти между сессиями, что важно для долгосрочных взаимодействий.

```python
# Сохранение памяти
saved_dict = conversation.memory.chat_memory.dict()

# Загрузка памяти
from langchain.memory import ChatMessageHistory
chat_memory = ChatMessageHistory(**saved_dict)
memory = ConversationBufferMemory(chat_memory=chat_memory)
```

## Реализации в LangGraph

LangGraph расширяет возможности LangChain, предоставляя более гибкие инструменты для создания мультиагентных систем с памятью.

### Долгосрочная память в LangGraph

LangGraph предоставляет механизмы для реализации долгосрочной памяти через систему чекпоинтов и сохранения состояния.

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

memory_saver = MemorySaver()
workflow = StateGraph()
# ... определение графа ...
compiled_graph = workflow.compile(checkpointer=memory_saver)
```

### Интеграция с RAG

LangGraph хорошо интегрируется с RAG-подходом, позволяя агентам извлекать информацию из внешних источников и истории взаимодействий.

```python
from langgraph.graph import StateGraph, START
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

class State(TypedDict):
    messages: List[Union[HumanMessage, AIMessage, ToolMessage]]
    context: List[Document]

def retrieve(state: State):
    query = state["messages"][-1].content
    docs = vector_store.similarity_search(query)
    return {"context": docs}

workflow = StateGraph(State)
workflow.add_node("retrieve", retrieve)
# ... определение остальных узлов и связей ...
```

### Управление состоянием

LangGraph предоставляет гибкие механизмы для управления состоянием агентов, что позволяет реализовать сложные схемы памяти.

```python
from langgraph.graph import StateGraph
from typing import TypedDict, List

class AgentState(TypedDict):
    messages: List
    memory: dict

def update_memory(state: AgentState):
    # Логика обновления памяти
    return {"memory": updated_memory}

workflow = StateGraph(AgentState)
workflow.add_node("update_memory", update_memory)
# ... определение остальных узлов и связей ...
```

## Примеры кода

### Базовая реализация памяти

Простая реализация памяти с использованием буфера:

```python
import os
from openai import OpenAI

# Инициализация клиента OpenAI
client = OpenAI()

prompt = """System: This is a conversation between a software engineer and   
intellectual AI bot. AI bot is talkative and teaches concepts to the engineer.  
Current Conversation:  
{history}  
Human: {input}  
AI:"""  
  
history = ''  
  
def talk(question):
    global history
      
    # Форматирование промпта с текущими значениями переменных
    prompt_after_formatting = prompt.format(input=question,
                                           history=history)
  
    # Вызов API
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt_after_formatting}
        ]
    )
  
    # Обработка ответа
    output = completion.choices[0].message.content
  
    # Добавление сообщений пользователя и ИИ в историю
    history += f"Human: {question}\nAI: {output}\n"
  
    return output
```

### Суммаризация истории

Реализация памяти с суммаризацией истории:

```python
import os
from openai import OpenAI

# Инициализация клиента OpenAI
client = OpenAI()

prompt = """System: This is a conversation between a software engineer and   
intellectual AI bot. AI bot is talkative and teaches concepts to the engineer.  
Current Conversation Summary:  
{summary}  
Human: {input}  
AI:"""  
  
summary_prompt = """System: Your task is to summarize below conversation with   
emphasis on key points. If nothing given, return ''.  
{history}  
Summary:"""  
  
history = ''  
  
def talk(question):
    global history
  
    # Форматирование промпта для суммаризации
    summary_prompt_after_formatting = summary_prompt.format(history=history)
  
    # Вызов API для суммаризации
    summary_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": summary_prompt_after_formatting}
        ]
    )
      
    # Обработка ответа
    summary = summary_completion.choices[0].message.content
  
    # Форматирование основного промпта
    prompt_after_formatting = prompt.format(input=question,
                                           summary=summary)
      
    # Вызов API для ответа на вопрос
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt_after_formatting}
        ]
    )
  
    # Обработка ответа
    output = completion.choices[0].message.content
    
    # Добавление сообщений пользователя и ИИ в историю
    history += f"Human: {question}\nAI: {output}\n"
  
    return output
```

### RAG-память

Реализация памяти с использованием RAG:

```python
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import uuid
from datetime import datetime

class RAGMemory:
    def __init__(self, collection_name="agent_memory"):
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.llm = ChatOpenAI()
    
    def add_memory(self, text, metadata=None):
        """Добавляет новую информацию в память"""
        if metadata is None:
            metadata = {"timestamp": str(datetime.now()), "id": str(uuid.uuid4())}
        
        # Разделение текста на чанки
        docs = self.text_splitter.create_documents([text], [metadata])
        
        # Добавление документов в векторное хранилище
        self.vector_store.add_documents(docs)
        
        return metadata["id"]
    
    def retrieve_relevant_memories(self, query, k=3):
        """Извлекает релевантные воспоминания на основе запроса"""
        docs = self.vector_store.similarity_search(query, k=k)
        return docs
    
    def summarize_memories(self, docs):
        """Суммирует извлеченные воспоминания"""
        if not docs:
            return "No relevant memories found."
        
        context = "\n\n".join([doc.page_content for doc in docs])
        prompt = f"""Summarize the following information concisely:
        
        {context}
        
        Summary:"""
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def query_memory(self, query):
        """Запрашивает память и возвращает релевантную информацию"""
        docs = self.retrieve_relevant_memories(query)
        summary = self.summarize_memories(docs)
        return summary
```

### Управление контекстным окном

Реализация управления размером контекстного окна:

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import tiktoken

class ContextWindowManager:
    def __init__(self, model_name="gpt-3.5-turbo", max_tokens=4000, buffer=500):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.buffer = buffer  # Буфер для новых сообщений
        self.encoding = tiktoken.encoding_for_model(model_name)
        self.llm = ChatOpenAI(model=model_name)
        self.system_message = SystemMessage(content="You are a helpful assistant.")
    
    def count_tokens(self, messages):
        """Подсчитывает количество токенов в сообщениях"""
        token_count = 0
        for message in messages:
            # Токены для метаданных сообщения
            token_count += 4  # Примерная стоимость метаданных
            # Токены для содержимого
            token_count += len(self.encoding.encode(message.content))
        return token_count
    
    def trim_messages(self, messages, max_tokens):
        """Обрезает список сообщений до указанного количества токенов"""
        # Всегда сохраняем системное сообщение
        result = [msg for msg in messages if isinstance(msg, SystemMessage)]
        
        # Добавляем остальные сообщения, начиная с самых новых
        other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        other_messages.reverse()  # Начинаем с самых новых
        
        current_tokens = self.count_tokens(result)
        
        for message in other_messages:
            message_tokens = len(self.encoding.encode(message.content))
            if current_tokens + message_tokens <= max_tokens:
                result.append(message)
                current_tokens += message_tokens
            else:
                # Если сообщение слишком большое, можно попробовать его суммаризовать
                break
        
        # Возвращаем сообщения в правильном порядке
        result = [msg for msg in result if isinstance(msg, SystemMessage)] + \
                [msg for msg in result if not isinstance(msg, SystemMessage)]
        
        return result
    
    def manage_context(self, messages, new_message):
        """Управляет контекстным окном при добавлении нового сообщения"""
        # Добавляем новое сообщение
        updated_messages = messages + [new_message]
        
        # Проверяем, не превышен ли лимит токенов
        current_tokens = self.count_tokens(updated_messages)
        available_tokens = self.max_tokens - self.buffer
        
        if current_tokens <= available_tokens:
            return updated_messages
        
        # Если превышен, пробуем обрезать историю
        trimmed_messages = self.trim_messages(messages, available_tokens - len(self.encoding.encode(new_message.content)))
        
        return trimmed_messages + [new_message]
```

### Иерархическая память

Реализация иерархической памяти, сочетающей краткосрочную и долгосрочную память:

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import tiktoken
from datetime import datetime
import uuid

class HierarchicalMemory:
    def __init__(self, model_name="gpt-3.5-turbo", max_tokens=4000):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.encoding = tiktoken.encoding_for_model(model_name)
        self.llm = ChatOpenAI(model=model_name)
        
        # Краткосрочная память (текущий разговор)
        self.short_term_memory = []
        
        # Долгосрочная память (векторное хранилище)
        self.embeddings = OpenAIEmbeddings()
        self.long_term_memory = Chroma(
            collection_name="hierarchical_memory",
            embedding_function=self.embeddings
        )
    
    def count_tokens(self, messages):
        """Подсчитывает количество токенов в сообщениях"""
        token_count = 0
        for message in messages:
            token_count += 4  # Примерная стоимость метаданных
            token_count += len(self.encoding.encode(message.content))
        return token_count
    
    def add_to_short_term_memory(self, message):
        """Добавляет сообщение в краткосрочную память"""
        self.short_term_memory.append(message)
        
        # Проверяем, не превышен ли лимит токенов
        if self.count_tokens(self.short_term_memory) > self.max_tokens * 0.8:
            self.consolidate_memory()
    
    def consolidate_memory(self):
        """Консолидирует краткосрочную память в долгосрочную"""
        # Создаем суммаризацию текущего разговора
        conversation = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in self.short_term_memory])
        summary_prompt = f"""Extract key information from this conversation that would be useful to remember for future interactions:
        
        {conversation}
        
        Key information (in bullet points):"""
        
        summary = self.llm.invoke([HumanMessage(content=summary_prompt)])
        
        # Сохраняем суммаризацию в долгосрочной памяти
        metadata = {
            "timestamp": str(datetime.now()),
            "id": str(uuid.uuid4()),
            "type": "conversation_summary"
        }
        
        self.long_term_memory.add_texts(
            texts=[summary.content],
            metadatas=[metadata]
        )
        
        # Оставляем только последние несколько сообщений в краткосрочной памяти
        system_messages = [msg for msg in self.short_term_memory if isinstance(msg, SystemMessage)]
        other_messages = [msg for msg in self.short_term_memory if not isinstance(msg, SystemMessage)]
        
        # Оставляем только последние 4 сообщения (2 обмена)
        if len(other_messages) > 4:
            other_messages = other_messages[-4:]
        
        # Добавляем суммаризацию как системное сообщение
        summary_message = SystemMessage(content=f"Previous conversation summary: {summary.content}")
        
        self.short_term_memory = system_messages + [summary_message] + other_messages
    
    def retrieve_from_long_term_memory(self, query, k=3):
        """Извлекает релевантную информацию из долгосрочной памяти"""
        docs = self.long_term_memory.similarity_search(query, k=k)
        return docs
    
    def process_input(self, user_input):
        """Обрабатывает ввод пользователя с использованием иерархической памяти"""
        # Добавляем сообщение пользователя в краткосрочную память
        user_message = HumanMessage(content=user_input)
        self.add_to_short_term_memory(user_message)
        
        # Извлекаем релевантную информацию из долгосрочной памяти
        relevant_docs = self.retrieve_from_long_term_memory(user_input)
        relevant_info = "\n".join([doc.page_content for doc in relevant_docs])
        
        # Если есть релевантная информация, добавляем её как контекст
        if relevant_info.strip():
            context_message = SystemMessage(content=f"Relevant information from past conversations: {relevant_info}")
            context_messages = self.short_term_memory + [context_message]
        else:
            context_messages = self.short_term_memory
        
        # Получаем ответ от модели
        response = self.llm.invoke(context_messages)
        
        # Добавляем ответ в краткосрочную память
        ai_message = AIMessage(content=response.content)
        self.add_to_short_term_memory(ai_message)
        
        return response.content
```

## Рекомендации и лучшие практики

На основе проведенного исследования, можно выделить следующие рекомендации для реализации памяти в мультиагентных системах:

1. **Выбор подхода в зависимости от сценария**:
   - Для коротких диалогов: ConversationBufferMemory
   - Для средних диалогов: ConversationSummaryMemory
   - Для длительных взаимодействий: RAG или иерархическая память

2. **Оптимизация использования токенов**:
   - Используйте суммаризацию для сжатия истории
   - Извлекайте только релевантную информацию из долгосрочной памяти
   - Динамически управляйте размером контекста

3. **Структурирование памяти**:
   - Разделяйте память на краткосрочную и долгосрочную
   - Используйте метаданные для организации информации
   - Применяйте фильтрацию для извлечения наиболее релевантной информации

4. **Интеграция с мультиагентными системами**:
   - Используйте общую память для обмена информацией между агентами
   - Применяйте специализированные типы памяти для разных агентов
   - Обеспечьте механизмы синхронизации памяти

5. **Тестирование и оптимизация**:
   - Регулярно проверяйте эффективность извлечения информации
   - Оптимизируйте параметры (размер чанков, перекрытие, количество извлекаемых документов)
   - Мониторьте использование токенов и стоимость запросов

## Заключение

Реализация эффективной памяти является ключевым аспектом создания мультиагентных систем, способных поддерживать длительные и сложные взаимодействия. В данном отчете мы рассмотрели различные подходы к решению этой задачи, от простых буферных реализаций до сложных иерархических систем с использованием RAG.

Библиотеки LangChain и LangGraph предоставляют мощные инструменты для реализации различных типов памяти, которые можно адаптировать под конкретные требования проекта. Выбор оптимального подхода зависит от специфики задачи, ожидаемой длительности взаимодействий и требований к сохранению контекста.

Наиболее перспективными подходами являются:
1. Использование RAG для долгосрочной памяти
2. Иерархические системы памяти, сочетающие различные типы хранения
3. Динамическое управление контекстным окном

Эти подходы позволяют эффективно балансировать между сохранением релевантной информации и оптимизацией использования контекстного окна, что критически важно для создания масштабируемых и экономически эффективных мультиагентных систем.

## Ссылки

1. [LangChain Documentation - Memory](https://python.langchain.com/v0.1/docs/modules/memory/)
2. [LangGraph Documentation - Memory](https://langchain-ai.github.io/langgraph/concepts/memory/)
3. [Retrieval Augmented Generation with LangGraph Agents](https://wellsr.com/python/retrieval-augmented-generation-with-langgraph-agents/)
4. [LangChain Memory and Agents Simplified](https://medium.com/@gokberkozsoy/langchain-memory-and-agents-simplified-129b065259e5)
5. [How to persist LangChain conversation memory](https://stackoverflow.com/questions/75965605/how-to-persist-langchain-conversation-memory-save-and-load)
6. [Build a Retrieval Augmented Generation (RAG) App: Part 2](https://python.langchain.com/docs/tutorials/qa_chat_history/)
7. [Launching Long-Term Memory Support in LangGraph](https://blog.langchain.dev/launching-long-term-memory-support-in-langgraph/)
