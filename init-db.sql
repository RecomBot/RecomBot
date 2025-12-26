# init-db.sql
-- Скрипт инициализации базы данных
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Создаем базовые роли пользователей
DO $$
BEGIN
    -- Проверяем и создаем роли, если их нет
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travel_app') THEN
        CREATE ROLE travel_app WITH LOGIN PASSWORD 'travel_app_password';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'travel_parser') THEN
        CREATE ROLE travel_parser WITH LOGIN PASSWORD 'travel_parser_password';
    END IF;
    
    -- Даем права
    GRANT CONNECT ON DATABASE travel_db TO travel_app, travel_parser;
    GRANT USAGE ON SCHEMA public TO travel_app, travel_parser;
    GRANT CREATE ON SCHEMA public TO travel_app;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Ошибка при создании ролей: %', SQLERRM;
END $$;