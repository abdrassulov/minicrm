Мини-CRM для распределения лидов

Система автоматически распределяет входящие обращения между операторами с учётом их загрузки и весов по источникам.

Быстрый запуск
Локально

pip install -r requirements.txt
uvicorn main:app --reload

Docker

docker build -t mini-crm .
docker run -p 8000:8000 mini-crm

Docker Compose (рекомендуется)

docker-compose up -d
docker-compose down
docker-compose logs -f

Доступ к приложению

http://localhost:8000

Swagger: /docs
ReDoc: /redoc

Быстрое тестирование

chmod +x test_requests.sh
./test_requests.sh

Основные модели
Operator

id, name, is_active, max_load

Lead

id, external_id, name, phone, email

Source

id, name, description

SourceOperatorConfig

source_id, operator_id, weight

Contact

lead_id, source_id, operator_id, message, is_active, created_at

Логика распределения

По external_id ищется существующий лид или создаётся новый.

Для источника выбираются активные операторы с загрузкой ниже max_load.

Выполняется взвешенный случайный выбор оператора по их "weight".

Контакт создаётся всегда — с оператором или без (если нет доступных).

API
Операторы

POST /operators/
GET /operators/
PATCH /operators/{id}

Источники

POST /sources/
GET /sources/

Настройка распределения

POST /sources/{id}/operators/
GET /sources/{id}/operators/

Контакты (главный endpoint)

POST /contacts/

Пример:
{
"lead_external_id": "tg_123",
"source_id": 1,
"message": "Здравствуйте",
"lead_name": "Иван"
}

Дополнительно

GET /contacts/
GET /leads/
GET /leads/{id}/contacts/
GET /statistics/

Особенности системы

Повторный лид с тем же external_id не создаётся.

Веса конфигураций применяются сразу.

Система создаёт контакт даже при отсутствии доступного оператора.

SQLite по умолчанию, легко заменить на PostgreSQL.

Алгоритм распределения масштабируем и эффективен.

Возможные улучшения

Пагинация списков

Переназначение обращений

История статусов

Мониторинг

Автотесты

Alembic миграции
