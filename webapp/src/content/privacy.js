// Политика конфиденциальности платформы Botify. English governs — русская
// версия для удобства (см. Terms of Service, п. 1.3). Форма данных согласована
// с LegalModal.vue: notice + sections[{title, items}].
export const PRIVACY = {
  ru: {
    modalTitle: 'Политика конфиденциальности',
    notice:
      'Настоящая Политика конфиденциальности объясняет, какие данные собирает платформа Botify («Botify», «мы») при пользовании Сервисом, как они используются и передаются и какие у вас есть права. Политика является частью Условий использования. Пользуясь Сервисом, вы подтверждаете, что ознакомились с Политикой и согласны на сбор и использование данных, как описано здесь. Если вы не согласны — вы обязаны прекратить пользоваться Сервисом.',
    sections: [
      {
        title: 'О чём эта политика',
        items: [
          '1.1. Политика охватывает платформу Botify и все созданные на ней магазины. Продавцы — самостоятельные лица: каждый продавец сам решает, как обращаться с данными покупателей, полученными через его магазин (например, данными доставки), и сам отвечает за такую обработку по своим условиям и применимому праву.',
          '1.2. Сервис не предназначен для лиц младше 18 лет (см. раздел 8).',
        ],
      },
      {
        title: 'Какие данные мы собираем',
        items: [
          '2.1. Из Telegram: ваш идентификатор пользователя Telegram, имя и фамилию, юзернейм, фото профиля и язык клиента Telegram. Мы получаем их, когда вы открываете бота магазина или Mini App.',
          '2.2. От вас: выбранный вами язык интерфейса; ваши заказы (товары, суммы, статус, данные доставки, которые запрашивает продавец, — например адрес или телефон); сообщения и фото, которые вы отправляете в чатах заказов; ваши отзывы и оценки (продавцу видно ваше имя в Telegram, другим покупателям — псевдоним или отображаемое имя в зависимости от контекста); тема оформления.',
          '2.3. От продавцов: настройки магазина, карточки товаров, токен бота магазина (хранится в зашифрованном виде), сообщения и фото, отправляемые в чатах заказов.',
          '2.4. Технические данные: журналы и диагностика Сервиса (например, время и результат запросов), необходимые для работы и защиты Сервиса.',
        ],
      },
      {
        title: 'Как мы используем данные',
        items: [
          '3.1. Для работы Сервиса: создание и обработка заказов, показ ваших покупок, доставка сообщений и фото в чатах, отправка уведомлений (об оплате, отправке и других событиях), запоминание вашего языка и темы.',
          '3.2. Для безопасности и модерации: выявление и предотвращение мошенничества, злоупотреблений и нарушений Условий; модерация отзывов.',
          '3.3. Для агрегированной статистики: количества и суммы, не идентифицирующие вас лично (например, продажи магазина).',
          '3.4. Для соблюдения закона и защиты наших Условий.',
          '3.5. Мы не продаём ваши данные и не используем их для чужой рекламы.',
        ],
      },
      {
        title: 'Передача данных',
        items: [
          '4.1. Продавцу магазина, в котором вы покупаете: он видит заказы в своём магазине, данные доставки, указанные при оформлении, ваши сообщения и фото в чате заказа и ваши отзывы о его товарах. Продавцы независимы от Botify.',
          '4.2. Платёжным провайдерам (например, Crypto Pay): платёжные операции выполняют они; обработка ими платёжных данных регулируется их собственными правилами. Botify не получает реквизиты ваших карт или кошельков.',
          '4.3. Провайдерам инфраструктуры: хостинг и сервисы связи, используемые для работы Сервиса.',
          '4.4. Государственным органам: когда мы обязаны по закону или считаем необходимым для защиты прав, имущества или безопасности.',
          '4.5. Публично: ваши отзывы видят другие пользователи магазина (ваше имя в Telegram другим покупателям не показывается); остальное о вас публичным не является.',
        ],
      },
      {
        title: 'Хранение данных',
        items: [
          '5.1. Мы храним ваши данные, пока существует ваш аккаунт и пока заказы, чаты и отзывы могут понадобиться для работы Сервиса (включая встроенные в Сервис ограничения срока чатов заказов).',
          '5.2. После прекращения пользования или запроса на удаление мы удаляем или обезличиваем данные — кроме того, что обязаны хранить по закону или для законного учёта (например, записи о платежах и спорах).',
          '5.3. Оставленные вами отзывы могут оставаться видимыми после удаления аккаунта — под псевдонимом.',
        ],
      },
      {
        title: 'Безопасность',
        items: [
          '6.1. Мы применяем технические и организационные меры, включая шифрование токенов ботов магазинов в базе данных и ограничение доступа к данным.',
          '6.2. Ни один способ передачи или хранения данных не является абсолютно безопасным. Мы не можем гарантировать абсолютную безопасность и в максимальной допустимой законом степени не отвечаем за несанкционированный доступ, вызванный обстоятельствами вне нашего разумного контроля (см. также Условия использования, разделы 8 и 9).',
        ],
      },
      {
        title: 'Ваши права и выбор',
        items: [
          '7.1. Язык и тему оформления можно менять в профиле в любой момент.',
          '7.2. Запросить доступ к своим данным, их исправление или удаление можно, связавшись с нашей поддержкой. Мы ответим в разумный срок. Часть данных может быть сохранена, как описано в разделе 5.',
          '7.3. Удалить аккаунт Telegram можно средствами самого Telegram; оставшиеся данные мы обработаем по правилам раздела 5.2.',
        ],
      },
      {
        title: 'Несовершеннолетние',
        items: [
          '8.1. Сервис предназначен для лиц от 18 лет. Мы сознательно не собираем данные лиц младше 18 лет. Если вы считаете, что такие данные были предоставлены, сообщите нам — мы их удалим.',
        ],
      },
      {
        title: 'Международная передача',
        items: [
          '9.1. Мы и наши провайдеры можем обрабатывать данные в странах, отличных от вашей. При передаче информации мы обеспечиваем надлежащие меры защиты. Пользуясь Сервисом, вы соглашаетесь на такую передачу и обработку.',
        ],
      },
      {
        title: 'Изменения политики',
        items: [
          '10.1. Мы можем обновлять Политику в любое время. Актуальная версия доступна в Сервисе. Существенные изменения доводятся до пользователей через Сервис. Продолжение пользования после вступления изменений в силу означает их принятие.',
        ],
      },
      {
        title: 'Контакт',
        items: [
          '11.1. Вопросы о приватности и запросы к данным — через наш канал поддержки или бота Botify в Telegram.',
        ],
      },
    ],
  },
  en: {
    modalTitle: 'Privacy Policy',
    notice:
      'This Privacy Policy explains what information the Botify platform ("Botify", "we") collects when you use the Service, how it is used and shared, and what rights you have. It forms part of the Terms of Service. By using the Service you confirm that you have read this Policy and agree to the collection and use of information as described here. If you do not agree, you must stop using the Service.',
    sections: [
      {
        title: 'Scope',
        items: [
          '1.1. This Policy covers the Botify platform and every shop created with it. Sellers are separate persons: each seller decides how they handle buyer data received through their shop (for example, delivery details) and is responsible for that handling under their own terms and applicable law.',
          '1.2. The Service is not directed at persons under 18 (see Section 8).',
        ],
      },
      {
        title: 'What We Collect',
        items: [
          '2.1. From Telegram: your Telegram user identifier, first and last name, username, profile photo and the language of your Telegram client. We receive them when you open a shop bot or the Mini App.',
          '2.2. From you: your manual language choice; your orders (items, amounts, status, delivery details the seller asks for, such as address or phone); messages and photos you send in order chats; your reviews and ratings (the seller sees your Telegram name, other buyers see a pseudonym or a display name depending on the context); your theme preference.',
          '2.3. From sellers: shop settings, product listings, the shop bot token (stored in encrypted form), messages and photos sent in order chats.',
          '2.4. Technical data: service logs and diagnostics (for example, the time and outcome of requests) needed to run and secure the Service.',
        ],
      },
      {
        title: 'How We Use Data',
        items: [
          '3.1. To operate the Service: creating and processing orders, showing your purchases, delivering chat messages and photos, sending notifications (about payment, shipping and other events), remembering your language and theme.',
          '3.2. For safety and moderation: detecting and preventing fraud, abuse and violations of the Terms; moderating reviews.',
          '3.3. For aggregate statistics: counts and sums that do not identify you personally (for example, shop sales).',
          '3.4. To comply with the law and enforce our Terms.',
          '3.5. We do not sell your personal data and do not use it for third-party advertising.',
        ],
      },
      {
        title: 'Sharing',
        items: [
          '4.1. With the seller of the shop you buy from: the seller sees the orders in their shop, the delivery details you provide at checkout, your messages and photos in the order chat, and your reviews of their goods. Sellers are independent of Botify.',
          '4.2. With payment providers (for example, Crypto Pay): payment operations are performed by them; their handling of payment data is governed by their own policies. Botify does not receive your card or wallet credentials.',
          '4.3. With infrastructure providers: hosting and communication services used to run the Service.',
          '4.4. With authorities: when we are legally obliged or consider it necessary to protect rights, property or safety.',
          '4.5. Publicly: your reviews are visible to other users of the shop (your Telegram name is not shown to other buyers); nothing else about you is public.',
        ],
      },
      {
        title: 'Retention',
        items: [
          '5.1. We keep your data while your account exists and while your orders, chats and reviews may be needed for the Service (including the chat time limits built into the Service).',
          '5.2. After you stop using the Service or ask us to delete your data, we delete or anonymise it — except what we must keep by law or for legitimate record-keeping (for example, records of payments and disputes).',
          '5.3. Reviews you leave may remain visible after your account is deleted — under a pseudonym.',
        ],
      },
      {
        title: 'Security',
        items: [
          '6.1. We apply technical and organisational measures, including encryption of shop bot tokens in our database and restricted access to data.',
          '6.2. No method of transmission or storage is completely secure. We cannot guarantee absolute security, and to the maximum extent permitted by law we are not liable for unauthorised access caused by events beyond our reasonable control (see also the Terms of Service, Sections 8 and 9).',
        ],
      },
      {
        title: 'Your Rights and Choices',
        items: [
          '7.1. You can change your language and theme in the profile at any time.',
          '7.2. You can request access to, correction or deletion of your personal data by contacting our support. We will respond within a reasonable time. Some data may be retained as described in Section 5.',
          '7.3. You can delete your Telegram account through Telegram itself; we will handle the remaining data as described in Section 5.2.',
        ],
      },
      {
        title: 'Children',
        items: [
          '8.1. The Service is intended for persons at least 18 years old. We do not knowingly collect data of persons under 18. If you believe such data has been provided, contact us and we will delete it.',
        ],
      },
      {
        title: 'International Transfers',
        items: [
          '9.1. We and our providers may process data in countries other than yours. Where information is transferred, we apply appropriate safeguards. By using the Service you consent to such transfer and processing.',
        ],
      },
      {
        title: 'Changes to This Policy',
        items: [
          '10.1. We may update this Policy at any time. The current version is available in the Service. Material changes are communicated through the Service. Continued use after changes take effect means acceptance.',
        ],
      },
      {
        title: 'Contact',
        items: [
          '11.1. Privacy questions and data requests — via our support channel or the Botify bot in Telegram.',
        ],
      },
    ],
  },
}
