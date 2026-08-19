telegram webApp, vue + pinia

###  Структура фронтенда проекта

```
└── tg-guides
	├── public
	├── src
	│   ├── api # API сущности проекта
	│   ├── assets # Статические ресурсы
	│   │   ├── fonts # Шрифты
	│   │   ├── icons # Иконки
	│   │   ├── img # Картинки
	│   │   └── style # Стили
	│   │       ├── _fonts.scss
	│   │       ├── _imports.scss
	│   │       ├── index.scss
	│   │       ├── _reset.scss
	│   │       └── _variables.scss
	│   ├── layouts # Лэйауты приложения
	│   │   └── AppLayout
	│   │       ├── AppLayout.scss
	│   │       └── AppLayout.vue
	│   │   └── ...
	│   ├── pages # Страницы приложения
	│   │   ├── PageName
	│   │   │   ├── PageName.scss
	│   │   │   └── PageName.vue
	│   │   └── ...
	│   ├── components # Компоненты приложения
	│   │   ├── ComponentName
	│   │   │   ├── ComponentName.scss
	│   │   │   └── ComponentName.vue
	│   │   └── ui # Простые элементы интерфейса
	│   │       └── icons
	│   │           ├── TelegramStar.scss
	│   │           └── TelegramStar.vue
	│   │   └── ...
	│   ├── i18n # Интернационализация
	│   ├── mocks # Тестовые данные для верстки
	│   ├── router # Маршруты приложения
	│   ├── services # API сущности сторонних сервисов
	│   ├── store # Хранилища приложения
	│   ├── utils # Утилиты/функции, часто используемые в проекте
	│   ├── App.vue
	│   └── main.js
	├── babel.config.js
	├── jsconfig.json
	└── vue.config.js
```
