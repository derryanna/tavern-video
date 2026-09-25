# 🎬 Видео — расширение SillyTavern

Кнопка **🎬** на каждой картинке, которую сгенерировал [SLAY Images](https://github.com/wewwaistyping/SLAYimages)
(`<img data-iig-instruction=…>` в тексте сообщения). Нажатие → vision-модель пишет промпт для
Wan 2.2 image-to-video и выбирает LoRA-сеты из каталога бриджа → попап с правкой → задача уходит на локальный бридж
(ПК с ComfyUI) → готовое видео прикрепляется к сообщению как обычное ST-видео (`message.extra.media`) и/или улетает в телеграм.
Кнопка **⏩** продолжает движение с последнего кадра готового ролика.

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
   текст `data-iig-instruction` (модели он отдаётся как «image-model tags, reference only») и текст сообщения без HTML (последние 1500 символов).
3. Vision-модели через выбранный профиль Connection Manager уходят два сообщения: `system` (промпт из настроек — формула Wan 2.2:
   один абзац, субъект → одно движение → вторичные движения → статичный кадр + свет; имён персонажей модель не получает и пишет
   «the man / the woman»; в конец дописывается блок `Available LoRA sets:` из каталога моста — по строке `name — triggers — hint` на сет)
   и `user` с частями `text` + `image_url` (data URL). Ожидается JSON `{"lora": ["set", …] | "set", "prompt": "..."}`:
   `lora` принимается и строкой, и массивом, неизвестные имена игнорируются; лишний текст/```json-обёртка вырезаются,
   при невалидном JSON весь ответ идёт как промпт без LoRA.
   Путь по умолчанию — `ConnectionManagerRequestService.sendRequest` (`/scripts/extensions/shared.js`). Если профиль не Chat Completion,
   запрос упал, или включён флажок «Слать запрос напрямую», используется прямой `POST /api/backends/chat-completions/generate`
   с `getRequestHeaders()`, `chat_completion_source` из профиля (для custom — `custom_url`/`model`/`secret_id`/прокси).
4. Попап (`callGenericPopup`), кнопки **Го / Отмена**:
   * **Промпт** — textarea.
   * **LoRA** — список галочек из каталога бриджа: имя, группа, триггер-слова и поле силы (предзаполнено из каталога);
     отмечены сеты, которые выбрала модель. В задачу уходит `lora: ["name:strength", …]` — несколько сетов сразу.
   * **Секунды** (1–10), **Разрешение** 480/720, **Seed** (пусто = случайный).
   * **Качество** — быстро / лучше (`quality: fast | hi`).
   * **Роликов** — 1–3 (`count`): создаётся N задач с разными seed (`seed`, `seed+1`, … если seed задан; иначе разные случайные),
     каждая опрашивается отдельно и прикрепляет своё видео к тому же сообщению.
   * **Негатив (дополнительно)** — `neg_extra`.
   * **32 fps** — интерполяция (`smooth: true`).
   * **Куда**: чат / телеграм / оба.
5. `POST {bridgeUrl}/video/jobs` → `{id}`; затем `GET {bridgeUrl}/video/jobs/{id}` каждые 5 с. Под картинкой одна строка статуса.
   Один ролик: `⏳ в очереди #2`, `🎬 рендерю 1:05`, `❌ <ошибка>`, `✅ видео готово`.
   Несколько роликов: `⏳ #1 в очереди · 🎬 #2 рендерю 0:40 · ✅ #3 видео готово` (номер = номер ролика в сообщении).
   Готовые ролики исчезают из строки через 15 с, ошибки висят 5 минут.
6. Когда `status: "done"` и назначение включает чат: скачивается `video_url` (с Bearer), `POST /api/files/upload`
   (`slayvideo_<ts>_<job>.mp4` → `/user/files/…`), в сообщение добавляется `extra.media.push({type: 'video', url, title})`
   (ровно так, как это делает `ensureMessageMediaIsArray`/`appendMediaToMessage` в `public/script.js` 1.18; на старых сборках без
   `extra.media` — `extra.video = path`), `saveChat()`, перерисовка медиа сообщения. Видео появляется под сообщением с родными
   контролами ST (лупа/подпись/удалить + `<video controls>`) и переживает перезагрузку.

### ⏩ Продолжить

Как только у сообщения есть готовый ролик, рядом с 🎬 появляется **⏩**, а под каждым прикреплённым видео — кнопка **⏩ Продолжить**.
⏩ у картинки продолжает *последний* готовый ролик, кнопка под видео — *именно этот* ролик.
По клику расширение забирает `GET {bridgeUrl}/video/jobs/<job_id>/last` (PNG последнего кадра, с Bearer), отдаёт его vision-модели
по тому же пайплайну (текст пользователя начинается с «Continue the motion from this frame, it is the last frame of the previous clip.»
плюс промпт предыдущего ролика), открывает тот же попап с заголовком «⏩ Продолжить» (превью = последний кадр) и шлёт
`POST /video/jobs` со `start_job: "<job_id>"` **без** `image`. Результат прикрепляется ещё одним видео к тому же сообщению и становится
новым «последним» роликом. Цепочка хранится в `extra.tavern_video.chain = [job ids]` (готовые задачи в порядке завершения).

### Что хранится в сообщении

```json
"tavern_video": {
  "jobs": { "<job id>": { "n": 1, "status": "queued|rendering|done|error", "deliver": "chat", "prompt": "...", "src": "/user/images/…png",
                          "seed": 1234, "quality": "hi", "smooth": true, "start_job": "<job id>|undefined", "video": "/user/files/…mp4", "error": "…" } },
  "chain": ["<job id>", "…"],
  "job_id": "<последняя созданная задача>", "status": "…", "src": "/user/images/…png"
}
```

Поэтому если перезагрузить страницу или сменить чат во время рендера, опрос всех незавершённых задач продолжится,
а видео прикрепятся, когда чат снова открыт. Записи старого формата (одна задача: `job_id`/`status`) читаются и переводятся в новый вид.

## Настройки (Extensions → 🎬 Видео)

| Поле | Что это | По умолчанию |
|---|---|---|
| Адрес бриджа | Относительный путь на том же origin, что ST (`/comfy-bridge`, удобно через reverse-proxy) или полный URL (`http://192.168.0.5:8787`). Для другого origin бриджу нужен CORS (см. ниже). | `/comfy-bridge` |
| Ключ бриджа | Поле-пароль (кнопка-глаз показывает его), уходит как `Authorization: Bearer <ключ>` во все запросы к бриджу. Если пусто, берётся ключ SLAY Images — когда её endpoint указывает на тот же путь моста (сравнение без хоста и без ведущего слэша). | пусто |
| Профиль подключения | Профиль Connection Manager с vision-моделью. | — |
| Слать запрос напрямую | Обход `ConnectionManagerRequestService`: прямой POST в `/api/backends/chat-completions/generate` (если по обычному пути модель «не видит» картинку). | выкл |
| Тест | Кнопка: `GET {bridgeUrl}/` → ожидается `{"ok": true, "comfy": "<версия ComfyUI>"}`; результат показывается тостом. | — |
| Секунды / Разрешение | Длина ролика (1–10) и `res` (480/720) по умолчанию для попапа. | 5 / 480 |
| Качество / Роликов | Значения по умолчанию для `quality` (быстро = `fast`, лучше = `hi`) и `count` (1–3). | быстро / 1 |
| 32 fps | Интерполяция по умолчанию (`smooth`). | выкл |
| Негатив (дополнительно) | `neg_extra` по умолчанию. | пусто |
| Куда отправлять | `chat` / `tg` / `both` — значение радио по умолчанию. | чат |
| Системный промпт | Текст system-сообщения для vision-модели (без блока каталога — он дописывается сам), кнопка **сброс** возвращает промпт по умолчанию. Сохранённые копии старых промптов (с `{NAMES}` или жёстко прописанными `none\|nsfw\|dreamlay`) заменяются на актуальный автоматически. | см. `DEFAULT_SYSTEM_PROMPT` в `index.js` |
| Каталог LoRA | Только чтение: что бридж отдал по `GET /video/loras`. Перечитывается при открытии панели настроек и по кнопке **обновить**; иначе кэшируется на время жизни страницы. | — |

Всё хранится в `extension_settings['tavern_video']`, сохраняется через `saveSettingsDebounced()`.

## Контракт бриджа (API)

Все запросы к бриджу идут с заголовком `Authorization: Bearer {bridgeKey}` (если ключ задан) и `Content-Type: application/json`.

### `GET {bridgeUrl}/video/loras` — каталог LoRA

```json
{ "loras": [ { "name": "dreamlay", "triggers": ["bl0wj0b", "d0gg1e"], "hint": "explicit sex acts", "strength": 0.9, "group": "explicit" } ] }
```

`name` обязателен; `triggers` (массив или строка через запятую), `hint`, `strength` (по умолчанию 1.0), `group` — опциональны.
Расширение кэширует ответ на страницу, обновляет при открытии настроек.

### `POST {bridgeUrl}/video/jobs` — создать задачу

```json
{
  "image": "<base64 без префикса data:>",
  "image_mime": "image/png",
  "prompt": "Anime style. ... camera static, smooth continuous motion",
  "sec": 5,
  "res": 480,
  "seed": null,
  "lora": ["dreamlay:0.9", "nsfw:1.0"],
  "quality": "fast",
  "smooth": false,
  "neg_extra": "blurry, text",
  "deliver": "chat",
  "chat": "<context.chatId>",
  "message_id": 12
}
```

* `image` — PNG или JPEG в base64 (оригинальное разрешение картинки из чата). Бридж должен принимать и вариант с префиксом `data:image/png;base64,…`.
  **Либо** вместо `image` — `"start_job": "<job id>"`: продолжить с последнего кадра этой (готовой) задачи.
* `seed` — целое или `null` (случайный). При «Роликов» > 1 расширение само раздаёт разные seed.
* `lora` — массив строк `имя:сила`, может быть несколько сетов; если ни одного — `[]`.
* `quality` — `"fast" | "hi"`; `smooth` — `true|false` (интерполяция до 32 fps); `neg_extra` — строка (поле отсутствует, если пусто).
* `deliver` — `"chat" | "tg" | "both"`.
* `chat`, `message_id` — идентификатор чата ST и индекс сообщения (нужны бриджу для телеграма/логов).

Ответ: `200 {"id": "<job id>"}`. Ошибка: любой не-2xx, тело `{"error": "..."}` — текст покажется под картинкой.

### `GET {bridgeUrl}/video/jobs/{id}` — статус

```json
{ "status": "queued|rendering|done|error", "position": 2, "elapsed": 65.3, "error": null,
  "video_url": "/video/jobs/<id>/file", "quality": "fast", "smooth": false, "start_job": null }
```

* `position` — место в очереди (для `queued`), `elapsed` — секунды рендера (для `rendering`/`done`).
* `video_url` — абсолютный URL **или** путь: путь дописывается к `bridgeUrl` (если он уже начинается с пути бриджа, например
  `/comfy-bridge/video/...`, используется как есть). Скачивается `GET`-ом с тем же Bearer, ожидается `video/mp4`.
* При `error` — `error` с текстом.
* `quality`, `smooth`, `start_job` — эхо параметров задачи.

Расширение опрашивает статус каждые 5 с; после 6 подряд сетевых ошибок задача считается провалившейся (`❌ бридж недоступен`).

### `GET {bridgeUrl}/video/jobs/{id}/last` — последний кадр

PNG последнего кадра готовой задачи (Bearer). Используется кнопкой ⏩ как кадр для vision-модели. Не готово → не-2xx.

### `GET {bridgeUrl}/` — проверка связи

`{"ok": true, "comfy": "<версия ComfyUI>"}` — используется кнопкой **Тест** в настройках.

### CORS

Если бридж на другом origin (не через reverse-proxy ST), он должен отвечать на `OPTIONS` и отдавать
`Access-Control-Allow-Origin: *` (или origin ST), `Access-Control-Allow-Headers: Authorization, Content-Type`,
`Access-Control-Allow-Methods: GET, POST, OPTIONS`. Мок это делает.

## Мок бриджа (для тестов без GPU)

`mock/server.py` — только стандартная библиотека Python 3, реализует весь контракт выше:

```bash
python3 mock/server.py --port 8787 --key test-key            # queue 2 c + render 8 c, потом маленький mp4
python3 mock/server.py --render-seconds 3 --video my.mp4     # своё видео
python3 mock/server.py --prefix /comfy-bridge                # если ST проксирует /comfy-bridge → бридж
python3 mock/server.py --fail                                # каждая задача заканчивается ошибкой
```

* Каталог: `nsfw` (без триггеров), `dreamlay` (с триггер-словами, сила 0.9), `slow_pan` (группа camera). Неизвестный сет в `lora` → 400.
* `quality`/`smooth`/`neg_extra` валидируются и возвращаются в статусе; `start_job` должен указывать на готовую задачу, `image` при этом не нужен.
* `GET /video/jobs/<id>/last` отдаёт сгенерированный PNG 96×64.
* Фейковая vision-модель: `POST /v1/chat/completions` (OpenAI-формат) отвечает JSON `{"lora": ["nsfw", "unknown_set"], "prompt": "..."}`
  и в промпт вписывает, дошла ли картинка (`image received: image/png, 512x384`); на запрос-продолжение («Continue the motion…»)
  отвечает `"lora": "nsfw"` строкой и другим текстом. `GET /v1/models` отдаёт `mock-vision`.
* Промпт с `[fail]` завершает рендер ошибкой — удобно проверять `❌`.
* `GET /` отвечает `{"ok": true, "comfy": "mock"}` для кнопки **Тест**.

Настройки ST для мока: Connection Manager → профиль **custom**, URL `http://127.0.0.1:8787/v1`, модель `mock-vision`;
🎬 Видео → адрес `http://127.0.0.1:8787`, ключ `test-key`.

### Как тестировалось

SillyTavern 1.18.0 запущен из чистого клона, расширение положено в `data/default-user/extensions/tavern-video`,
в чат Серафины добавлены сообщения с `<img src="/user/images/…png" data-iig-instruction="test">` (одно из них — с записью
`tavern_video` старого формата). Playwright (Chromium) прогоняет против мока:

* каталог LoRA виден в настройках и в попапе (галочки = выбор модели, `unknown_set` проигнорирован, сила из каталога, триггеры показаны);
* два ролика за раз: seed 1234/1235, `quality: hi`, `smooth: true`, `neg_extra`, `lora: ["nsfw:1.0","dreamlay:0.75"]`, `deliver: both`,
  строка статуса `⏳ #1 в очереди · ⏳ #2 в очереди` → `✅ #1 видео готово · ✅ #2 видео готово`, два `<video>` в сообщении;
* ⏩: последний кадр (PNG 96×64) дошёл до модели, строковый `lora` принят, `POST` со `start_job` без `image`, третье видео,
  `chain` из трёх id, кнопки под каждым видео указывают на свою задачу, ⏩ у картинки — на последнюю;
* Отмена без создания задачи, `❌` при ошибке рендера (цепочка не меняется), доставка только в телеграм (без видео в чате),
  перезагрузка страницы посреди рендера (опрос возобновляется, видео прикрепляется), запись старого формата даёт ⏩,
  прямой путь запроса к модели.

## Файлы

* `manifest.json`, `index.js`, `style.css` — само расширение (корень репозитория).
* `mock/server.py` — мок бриджа + фейковая vision-модель.
