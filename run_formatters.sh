#!/bin/bash

# Получаем список измененных файлов в текущем коммите
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=d | grep "\.py$")

if [ -z "$CHANGED_FILES" ]; then
    echo "No Python files changed, skipping formatting checks"
    exit 0
fi

echo "Running formatters on changed files..."

# Запускаем black в режиме проверки
echo "Running black formatter..."
black --check $CHANGED_FILES
BLACK_RESULT=$?

# Запускаем isort в режиме проверки
echo "Running isort formatter..."
isort --check-only $CHANGED_FILES
ISORT_RESULT=$?

# Если что-то было отформатировано
if [ $BLACK_RESULT -eq 1 ] || [ $ISORT_RESULT -eq 1 ]; then
    echo -e "\e[33mSome files need formatting. Please run formatters and commit again.\e[0m"
    echo -e "\e[33mTo format files, run:\e[0m"
    echo -e "\e[33mblack $CHANGED_FILES\e[0m"
    echo -e "\e[33misort $CHANGED_FILES\e[0m"
    echo -e "\e[33m\e[0m"
    echo -e "\e[33mThen commit again:\e[0m"
    echo -e "\e[33mgit add .\e[0m"
    echo -e "\e[33mgit commit -m \"your message\"\e[0m"
    exit 1
fi

echo "✅ All files are properly formatted"
exit 0 