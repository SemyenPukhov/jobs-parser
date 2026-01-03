# Как добавить новую переменную окружения

При добавлении новой env переменной нужно обновить **3 файла**:

## 1. `backend/app/config.py`

Добавить в класс `Settings`:

```python
# Комментарий что это за переменная
MY_NEW_VAR: str | None = os.getenv("MY_NEW_VAR")
```

## 2. `.github/workflows/deploy.yml`

Добавить в секцию создания `.env` файла (строка ~54):

```yaml
cat > .env << EOL
...
MY_NEW_VAR=${{ secrets.MY_NEW_VAR }}
EOL
```

## 3. `docker-compose.prod.yml`

Добавить в секцию `backend` -> `environment`:

```yaml
backend:
  environment:
    ...
    MY_NEW_VAR: ${MY_NEW_VAR}
```

## 4. GitHub Secrets

Добавить secret в репозитории:
- Settings → Secrets and variables → Actions → New repository secret
- Или через environment secrets в `deploy-jobs-parser`

---

## Чеклист

- [ ] `backend/app/config.py` - определение переменной
- [ ] `.github/workflows/deploy.yml` - запись в .env при деплое  
- [ ] `docker-compose.prod.yml` - проброс в контейнер
- [ ] GitHub Secrets - значение переменной

**Если забыть любой из пунктов — переменная не будет доступна в контейнере!**

---

## Текущие переменные

| Переменная | Описание |
|------------|----------|
| `DB_USER`, `DB_PASSWORD`, `DB_NAME` | База данных |
| `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_MANAGER_ID` | Slack уведомления |
| `JUST_REMOTE_LOGIN`, `JUST_REMOTE_PWD` | Парсер justremote.co |
| `RAPID_YCOMB_API_KEY` | RapidAPI для Y Combinator |
| `PROXY_USER`, `PROXY_PASS`, `PROXY_HOST` | Прокси |
| `OPENROUTER_API_KEY` | AI матчинг |
| `DEVELOPERS_API_URL` | URL API с резюме |
| `MATCHING_THRESHOLD_HIGH`, `MATCHING_THRESHOLD_LOW` | Пороги матчинга |
| `AMOCRM_TOKEN`, `AMOCRM_BASE_URL`, `AMOCRM_PIPELINE_ID` | AmoCRM интеграция |
| `ENVIRONMENT` | prod/dev |

