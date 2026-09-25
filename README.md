# 🎬 Видео — расширение SillyTavern

Кнопка **🎬** на каждой картинке, которую сгенерировал [SLAY Images](https://github.com/wewwaistyping/SLAYimages)
(`<img data-iig-instruction=…>` в тексте сообщения). Нажатие → vision-модель пишет промпт для
Wan 2.2 image-to-video → попап с правкой промпта → задача уходит на локальный бридж (ПК с ComfyUI) →
готовое видео прикрепляется к сообщению как обычное ST-видео (`message.extra.media`) и/или улетает в телеграм.

Целевая версия SillyTavern: **1.18.0** (проверено также на 1.19.0). Нужен встроенный **Connection Manager**
(включён по умолчанию).

## Установка

1. SillyTavern → **Extensions** (кубик) → **Install extension** → вставить URL:
   ```
   https://github.com/derryanna/tavern-video
   ```
2. Открыть настройки расширений, найти блок **🎬 Видео**, заполнить (см. ниже).
3. В **Connection Manager** должен быть профиль с vision-моделью (Chat Completion: custom / OpenAI / OpenRouter / Gemini / Claude и т.д.).

Никаких секретов в репозитории нет: ключ бриджа хранится только в настройках ST (`extension_settings.tavern_video`).

## Как это работает

1. Расширение сканирует чат (`CHAT_CHANGED`, `*_MESSAGE_RENDERED`, `MESSAGE_UPDATED`, `MESSAGE_SWIPED`, `MESSAGE_EDITED`, плюс `MutationObserver` на `#chat`,
   чтобы поймать картинку, которую SLAY дорисовал асинхронно) и вешает кнопку 🎬 в правый нижний угол каждой `img[data-iig-instruction]`
   (кнопка SLAY «перегенерировать» живёт слева сверху, они не пересекаются). Если SLAY уже обернул картинку в `.iig-img-wrap`,
   используется его обёртка, иначе создаётся своя `.tv-img-wrap`. Кнопка 40×40 px, на телефонах видна всегда.
2. По клику собираются: картинка (`fetch(src)` → base64, оригинальное разрешение; webp/gif перекодируются в PNG),
   текст `data-iig-instruction`, текст сообщения без HTML (последние 1500 символов), `context.name1` (юзер) и `context.name2` (персонаж).
3. Vision-модели через выбранный профиль Connection Manager уходят два сообщения: `system` (промпт из настроек; имён персонажей модель не получает и пишет «the man / the woman») и `user` с частями `text` + `image_url` (data URL). Ожидается JSON `{"lora":"none|nsfw|dreamlay","prompt":"..."}`;
   лишний текст/```json-обёртка вырезаются, при невалидном JSON весь ответ идёт как промпт, lora — из настроек.
   Путь по умолчанию — `ConnectionManagerRequestService.sendRequest` (`/scripts/extensions/shared.js`). Если профиль не Chat Completion,
   запрос упал, или включён флажок «Слать запрос напрямую», используется прямой `POST /api/backends/chat-completions/generate`
   с `getRequestHeaders()`, `chat_completion_source` из профиля (для custom — `custom_url`/`model`/`secret_id`/прокси).
4. Попап (`callGenericPopup`): промпт (textarea), LoRA (`none/nsfw/dreamlay`) + сила, секунды, разрешение 480/720, seed (пусто = случайный),
   куда: **чат / телеграм / оба**. Кнопки **Го / Отмена**.
5. `POST {bridgeUrl}/video/jobs` → `{id}`; затем `GET {bridgeUrl}/video/jobs/{id}` каждые 5 с. Под картинкой одна строка статуса:
   `⏳ в очереди #2`, `🎬 рендерю 1:05`, `❌ <ошибка>`, `✅ видео готово`.
6. Когда `status: "done"` и назначение включает чат: скачивается `video_url` (с Bearer), `POST /api/files/upload`
   (`slayvideo_<ts>.mp4` → `/user/files/…`), в сообщение добавляется `extra.media.push({type: 'video', url, title})`
   (ровно так, как это делает `ensureMessageMediaIsArray`/`appendMediaToMessage` в `public/script.js` 1.18; на старых сборках без
   `extra.media` — `extra.video = path`), `saveChat()`, перерисовка медиа сообщения. Видео появляется под сообщением с родными
   контролами ST (лупа/подпись/удалить + `<video controls>`) и переживает перезагрузку.

Состояние задачи пишется в `message.extra.tavern_video` (`job_id`, `status`, `deliver`, `prompt`, `src`, `video`), поэтому если перезагрузить
страницу или сменить чат во время рендера, опрос продолжится, а видео прикрепится, когда чат снова открыт.

## Настройки (Extensions → 🎬 Видео)

| Поле | Что это | По умолчанию |
|---|---|---|
| Адрес бриджа | Относительный путь на том же origin, что ST (`/comfy-bridge`, удобно через reverse-proxy) или полный URL (`http://192.168.0.5:8787`). Для другого origin бриджу нужен CORS (см. ниже). | `/comfy-bridge` |
| Ключ бриджа | Поле-пароль, уходит как `Authorization: Bearer <ключ>` во все запросы к бриджу. | пусто |
| Профиль подключения | Профиль Connection Manager с vision-моделью. | — |
| Слать запрос напрямую | Обход `ConnectionManagerRequestService`: прямой POST в `/api/backends/chat-completions/generate` (если по обычному пути модель «не видит» картинку). | выкл |
| Секунды / Разрешение | Длина ролика и `res` (480/720) по умолчанию для попапа. | 5 / 480 |
| LoRA по умолчанию / Сила | LoRA, если модель не вернула валидный JSON; сила добавляется как `lora:["dreamlay:1.0"]`. | none / 1.0 |
| Куда отправлять | `chat` / `tg` / `both` — значение радио по умолчанию. | чат |
| Системный промпт | Текст system-сообщения для vision-модели, кнопка **сброс** возвращает промпт по умолчанию. | см. `DEFAULT_SYSTEM_PROMPT` в `index.js` |

Всё хранится в `extension_settings['tavern_video']`, сохраняется через `saveSettingsDebounced()`.

## Контракт бриджа (API)

Все запросы к бриджу идут с заголовком `Authorization: Bearer {bridgeKey}` (если ключ задан) и `Content-Type: application/json`.

### `POST {bridgeUrl}/video/jobs` — создать задачу

```json
{
  "image": "<base64 без префикса data:>",
  "image_mime": "image/png",
  "prompt": "Anime style. ... camera static, smooth continuous motion",
  "sec": 5,
  "res": 480,
  "seed": null,
  "lora": ["dreamlay:1.0"],
  "deliver": "chat",
  "chat": "<context.chatId>",
  "message_id": 12
}
```

* `image` — PNG или JPEG в base64 (оригинальное разрешение картинки из чата). Бридж должен принимать и вариант с префиксом `data:image/png;base64,…`.
* `seed` — целое или `null` (случайный).
* `lora` — массив строк `имя:сила`; при `none` — пустой массив `[]`.
* `deliver` — `"chat" | "tg" | "both"`.
* `chat`, `message_id` — идентификатор чата ST и индекс сообщения (нужны бриджу для телеграма/логов).

Ответ: `200 {"id": "<job id>"}`. Ошибка: любой не-2xx, тело `{"error": "..."}` — текст покажется под картинкой.

### `GET {bridgeUrl}/video/jobs/{id}` — статус

```json
{ "status": "queued|rendering|done|error", "position": 2, "elapsed": 65.3, "error": null, "video_url": "/video/jobs/<id>/file" }
```

* `position` — место в очереди (для `queued`), `elapsed` — секунды рендера (для `rendering`/`done`).
* `video_url` — абсолютный URL **или** путь: путь дописывается к `bridgeUrl` (если он уже начинается с пути бриджа, например
  `/comfy-bridge/video/...`, используется как есть). Скачивается `GET`-ом с тем же Bearer, ожидается `video/mp4`.
* При `error` — `error` с текстом.

Расширение опрашивает статус каждые 5 с; после 6 подряд сетевых ошибок задача считается провалившейся (`❌ бридж недоступен`).

### CORS

Если бридж на другом origin (не через reverse-proxy ST), он должен отвечать на `OPTIONS` и отдавать
`Access-Control-Allow-Origin: *` (или origin ST), `Access-Control-Allow-Headers: Authorization, Content-Type`,
`Access-Control-Allow-Methods: GET, POST, OPTIONS`. Мок это делает.

## Мок бриджа (для тестов без GPU)

`mock/server.py` — только стандартная библиотека Python 3:

```bash
python3 mock/server.py --port 8787 --key test-key            # queue 2 c + render 8 c, потом маленький mp4
python3 mock/server.py --render-seconds 3 --video my.mp4     # своё видео
python3 mock/server.py --prefix /comfy-bridge                # если ST проксирует /comfy-bridge → бридж
python3 mock/server.py --fail                                # каждая задача заканчивается ошибкой
```

Кроме бриджа мок поднимает фейковую vision-модель: `POST /v1/chat/completions` (OpenAI-формат) отвечает JSON
`{"lora":"nsfw","prompt":"..."}` и в промпт вписывает, дошла ли картинка (`image received: image/png, 512x384`),
а `GET /v1/models` отдаёт `mock-vision`. Промпт с `[fail]` завершает рендер ошибкой — удобно проверять `❌`.

Настройки ST для мока: Connection Manager → профиль **custom**, URL `http://127.0.0.1:8787/v1`, модель `mock-vision`;
🎬 Видео → адрес `http://127.0.0.1:8787`, ключ `test-key`.

### Как тестировалось

SillyTavern 1.18.0 (и release 1.19.0) запущен из чистого клона, расширение положено в `data/default-user/extensions/tavern-video`,
в чат Серафины добавлено сообщение с `<img src="/user/images/…png" data-iig-instruction="test">`. Playwright (Chromium) кликает 🎬 →
попап с промптом мока (картинка дошла до модели по обоим путям — через Connection Manager и напрямую) → **Го** → статусы
`⏳ в очереди #1` → `🎬 рендерю 0:03` → `✅ видео готово`; в сообщении появляется `<video class="mes_video" controls>` с
`src=/user/files/slayvideo_<ts>.mp4`, файл лежит на диске, в `.jsonl` чата записано `extra.media: [{type:"video", url}]`,
после перезагрузки страницы видео на месте. Отдельно проверены **Отмена**, ошибка рендера и перезагрузка страницы посреди рендера
(опрос возобновляется, видео прикрепляется).

## Файлы

* `manifest.json`, `index.js`, `style.css` — само расширение (корень репозитория).
* `mock/server.py` — мок бриджа + фейковая vision-модель.
