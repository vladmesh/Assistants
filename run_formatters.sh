#!/bin/bash

# Получаем список измененных .py файлов, добавленных в индекс
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=d | grep "\\.py$")

if [ -z "$CHANGED_FILES" ]; then
    echo "No Python files staged for commit, skipping formatting."
    exit 0
fi

echo "Running formatters on staged files..."

# 1. Применяем black
echo "Running black formatter..."
black $CHANGED_FILES
BLACK_RESULT=$?

if [ $BLACK_RESULT -ne 0 ]; then
    echo -e "\\e[31mError running black formatter.\\e[0m"
    exit 1 # Выходим, если black завершился с ошибкой
fi

# 2. Применяем isort
echo "Running isort formatter..."
isort $CHANGED_FILES
ISORT_RESULT=$?

if [ $ISORT_RESULT -ne 0 ]; then
    echo -e "\\e[31mError running isort formatter.\\e[0m"
    exit 1 # Выходим, если isort завершился с ошибкой
fi

# 3. Добавляем отформатированные файлы обратно в индекс
echo "Adding formatted files back to the index..."
git add $CHANGED_FILES
ADD_RESULT=$?

if [ $ADD_RESULT -ne 0 ]; then
    echo -e "\\e[31mError adding formatted files back to index.\\e[0m"
    exit 1 # Выходим, если git add завершился с ошибкой
fi

echo "✅ Formatting applied and files staged."
exit 0 