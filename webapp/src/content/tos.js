// Условия использования платформы Botify для всех пользователей (покупателей
// и продавцов). English governs — русская версия для удобства (см. п. 1.3).
// Форма данных согласована с LegalModal.vue: notice + sections[{title, items}].
export const TOS = {
  ru: {
    modalTitle: 'Условия использования',
    notice:
      'ВАЖНО — ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО. Настоящие Условия использования («Условия») — юридически обязывающее соглашение между вами и Botify («Botify», «мы»). Открывая или используя платформу Botify — включая ботов магазинов, веб-приложение (Mini App), витрины, чаты и иные функции, работающие на платформе (вместе — «Сервис»), — вы подтверждаете, что прочитали, поняли и приняли настоящие Условия, включая пункт об обязательном индивидуальном арбитраже и отказе от групповых исков (раздел 12). Условия распространяются на всех пользователей Сервиса — и покупателей, и продавцов. Если вы не согласны хотя бы с частью Условий, вы обязаны немедленно прекратить пользоваться Сервисом.',
    sections: [
      {
        title: 'Принятие условий и изменения',
        items: [
          '1.1. Используя Сервис любым способом, вы принимаете настоящие Условия в полном объёме. Условия составляют полное соглашение между вами и Botify в отношении Сервиса и заменяют любые прежние договорённости.',
          '1.2. Мы можем изменять Условия в любое время по собственному усмотрению. Актуальная версия всегда доступна в Сервисе. Продолжая пользоваться Сервисом после вступления изменений в силу, вы принимаете изменённые Условия; если вы не согласны — вы обязаны прекратить пользоваться Сервисом.',
          '1.3. Условия заключены на английском языке. Любой перевод, включая русскую версию, приведён для удобства и не имеет юридической силы; при расхождениях преимущественную силу имеет английская версия.',
        ],
      },
      {
        title: 'Право доступа и учётные записи',
        items: [
          '2.1. Сервис доступен только лицам в возрасте 18 лет и старше. Используя Сервис, вы подтверждаете, что вам исполнилось 18 лет, и что использование Сервиса вами не нарушает применимое право.',
          '2.2. Для доступа к Сервису требуется аккаунт Telegram. Вы отвечаете за безопасность своего аккаунта Telegram и за все действия, совершаемые через него.',
          '2.3. Вы обязаны предоставлять достоверные данные там, где Сервис их запрашивает (например, данные доставки в заказе). Мы не обязаны их проверять.',
        ],
      },
      {
        title: 'Чем является Botify — и чем не является',
        items: [
          '3.1. Botify предоставляет техническую платформу, с помощью которой продавцы создают магазины внутри Telegram, а покупатели просматривают такие магазины, оформляют заказы, оплачивают их и общаются с продавцами.',
          '3.2. Botify не является продавцом, изготовителем, импортёром, перевозчиком или владельцем каких-либо товаров, показанных в магазинах. Botify не владеет магазинами и товарами, не является стороной сделки между покупателем и продавцом и не проверяет товары, продавцов, карточки товаров и доставку.',
          '3.3. Каждый продавец самостоятельно отвечает за свой магазин, его содержимое, предлагаемые товары, их качество и законность, доставку, возвраты и соблюдение применимого права. Любые претензии, связанные с покупкой, следует направлять соответствующему продавцу.',
          '3.4. Мы можем изменять, приостанавливать или прекращать работу любой части Сервиса в любое время, включая любые функции, без уведомления и без ответственности.',
        ],
      },
      {
        title: 'Покупки и платежи',
        items: [
          '4.1. Платежи обрабатываются сторонними платёжными провайдерами. Botify не получает, не хранит и не обрабатывает ваши платёжные реквизиты.',
          '4.2. Споры о платежах, возвраты и чарджбэки регулируются правилами соответствующего провайдера, а в части товаров — отношениями между покупателем и продавцом. Botify не обязан возвращать какие-либо платежи.',
          '4.3. Мы можем взимать с продавцов плату или комиссию за пользование Сервисом и изменять её в любое время.',
        ],
      },
      {
        title: 'Пользовательский контент',
        items: [
          '5.1. «Пользовательский контент» — любой контент, который вы отправляете через Сервис: тексты, отзывы, оценки, фото, сообщения в чатах, названия и описания магазинов, логотипы, карточки товаров и другие материалы.',
          '5.2. Права на ваш контент остаются за вами. Однако вы предоставляете Botify всемирную безвозмездную передаваемую лицензию с правом сублицензирования на размещение, хранение, копирование, воспроизведение, адаптацию, публикацию, распространение, показ и иное использование контента исключительно в целях работы, поддержки и развития Сервиса. Лицензия сохраняется и после прекращения вами пользования Сервисом — в объёме, необходимом для резервных копий и учёта.',
          '5.3. Вы полностью и единолично отвечаете за весь отправляемый вами контент. Botify не проводит предварительную модерацию и не одобряет контент.',
          '5.4. Мы можем, но не обязаны, отслеживать, модерировать, изменять или удалять любой контент в любое время по собственному усмотрению, с уведомлением или без, в частности при нарушении Условий или закона.',
        ],
      },
      {
        title: 'Запрещённое использование',
        items: [
          '6.1. Запрещается использовать Сервис, чтобы: нарушать закон или права третьих лиц; публиковать или распространять противоправный, мошеннический, клеветнический, непристойный, разжигающий ненависть, дискриминационный, угрожающий или нарушающий чужие права контент, включая нарушение авторских прав, товарных знаков и права на неприкосновенность частной жизни; продавать или продвигать запрещённые товары и услуги; рассылать спам и нежелательные коммерческие сообщения; распространять вредоносное программное обеспечение.',
          '6.2. Запрещается: вмешиваться в работу Сервиса и его инфраструктуры; пытаться получить несанкционированный доступ к Сервису, чужим аккаунтам или системам; собирать данные о других пользователях; реконструировать Сервис, кроме случаев, разрешённых законом; обходить любые лимиты, меры защиты и технические ограничения; выдавать себя за других лиц или вводить в заблуждение о своей принадлежности; использовать Сервис от лица несовершеннолетних.',
          '6.3. Мы можем проверять предположительные нарушения и сотрудничать с правоохранительными органами.',
        ],
      },
      {
        title: 'Интеллектуальная собственность',
        items: [
          '7.1. Сервис, включая его программный код, дизайн, интерфейс, тексты и бренд Botify, принадлежит Botify и охраняется законом об интеллектуальной собственности. Все права, не предоставленные явно, сохраняются за нами.',
          '7.2. Мы предоставляем вам ограниченную, отзывную, неисключительную и непередаваемую лицензию на использование Сервиса по назначению в соответствии с Условиями. Иные права не предоставляются.',
          '7.3. Если вы присылаете нам идеи, предложения или отзывы о Сервисе, вы предоставляете Botify ничем не ограниченное и бессрочное право использовать их без вознаграждения и указания авторства.',
        ],
      },
      {
        title: 'Отказ от гарантий — Сервис предоставляется «как есть»',
        items: [
          '8.1. СЕРВИС ПРЕДОСТАВЛЯЕТСЯ ПО ПРИНЦИПУ «КАК ЕСТЬ» (AS IS) И «ПО МЕРЕ ДОСТУПНОСТИ» (AS AVAILABLE), БЕЗ ГАРАНТИЙ ЛЮБОГО РОДА. В МАКСИМАЛЬНО ДОПУСТИМОЙ ЗАКОНОМ СТЕПЕНИ BOTIFY ОТКАЗЫВАЕТСЯ ОТ ВСЕХ ЯВНЫХ, ПОДРАЗУМЕВАЕМЫХ И ЗАКОНОДАТЕЛЬНЫХ ГАРАНТИЙ, ВКЛЮЧАЯ ГАРАНТИИ ТОВАРНОГО СОСТОЯНИЯ, ПРИГОДНОСТИ ДЛЯ КОНКРЕТНЫХ ЦЕЛЕЙ, НАЛИЧИЯ ПРАВ, ОТСУТСТВИЯ НАРУШЕНИЙ, ТОЧНОСТИ, БЕСПЕРЕБОЙНОЙ И БЕЗОШИБОЧНОЙ РАБОТЫ И БЕЗОПАСНОСТИ.',
          '8.2. Botify не гарантирует, что Сервис будет работать без перерывов, своевременно, безопасно и без ошибок, что дефекты будут исправлены; что Сервис и связь с ним свободны от вирусов и вредоносных компонентов; что данные (включая заказы, сообщения, файлы и статистику) не будут утрачены, повреждены или искажены; что будут достигнуты какие-либо результаты.',
          '8.3. Сервис зависит от третьих сторон (включая Telegram и платёжных провайдеров), чья работа, лимиты и правила находятся вне контроля Botify. Botify не отвечает за их действия, сбои, лимиты и блокировки.',
          '8.4. Вы пользуетесь Сервисом на свой риск. Вы единолично отвечаете за любой вред вашему устройству или данным, возникший в связи с использованием Сервиса.',
        ],
      },
      {
        title: 'Ограничение ответственности',
        items: [
          '9.1. В МАКСИМАЛЬНО ДОПУСТИМОЙ ЗАКОНОМ СТЕПЕНИ BOTIFY НЕ НЕСЁТ ПЕРЕД ВАМИ ОТВЕТСТВЕННОСТИ ЗА КОСВЕННЫЕ, СЛУЧАЙНЫЕ, СПЕЦИАЛЬНЫЕ, ПОСЛЕДСТВЕННЫЕ, ШТРАФНЫЕ ИЛИ ПРИМЕРНЫЕ УБЫТКИ, А ТАКЖЕ ЗА УПУЩЕННУЮ ВЫГОДУ, ПОТЕРЮ ВЫРУЧКИ, ДЕЛОВОЙ РЕПУТАЦИИ, ДАННЫХ, БИЗНЕСА ИЛИ ОЖИДАЕМОЙ ЭКОНОМИИ, ВОЗНИКШИЕ В СВЯЗИ С УСЛОВИЯМИ ИЛИ СЕРВИСОМ, — ДАЖЕ ЕСЛИ BOTIFY БЫЛО СООБЩЕНО О ВОЗМОЖНОСТИ ТАКИХ УБЫТКОВ И ДАЖЕ ЕСЛИ ИНОЕ СРЕДСТВО ЗАЩИТЫ НЕ ДОСТИГЛО СВОЕЙ ЦЕЛИ.',
          '9.2. В максимальной допустимой законом степени совокупная общая ответственность Botify перед вами по всем требованиям, связанным с Сервисом или Условиями, ограничена суммой двадцать долларов США (US$20). Лимит распространяется на все требования в совокупности — независимо от их правового основания, количества требований и событий — и не может быть увеличен никакими обстоятельствами.',
          '9.3. Ограничения этого раздела и раздела 8 применяются независимо от формы иска — договорной, деликтной (включая неосторожность) или иной — и являются существенной основой сделки между вами и Botify.',
          '9.4. Ничто в Условиях не исключает и не ограничивает ответственность, которую нельзя исключать или ограничивать по закону. В таких юрисдикциях исключения и лимиты применяются в максимальной степени, допустимой законом.',
        ],
      },
      {
        title: 'Возмещение ущерба',
        items: [
          '10.1. Вы соглашаетесь защищать, возмещать ущерб и ограждать Botify, её владельцев, операторов, сотрудников и подрядчиков от любых претензий, требований, исков, расследований, убытков, потерь, обязательств, штрафов, взысканий, издержек и расходов, включая разумные гонорары адвокатов и судебные или арбитражные расходы, возникающих в связи с: (a) вашим контентом; (b) вашим использованием Сервиса; (c) вашим нарушением Условий, закона или прав третьих лиц; (d) вашими сделками и взаимодействиями с другими пользователями, включая покупки и продажи; (e) любым утверждением о том, что ваше использование Сервиса причинило вред третьему лицу, включая претензии о клевете, нарушении прав или противоправном контенте.',
          '10.2. Мы вправе за свой счёт принять на себя исключительную защиту любого требования, подпадающего под возмещение. Вы обязуетесь сотрудничать с нами в защите. Вы не вправе урегулировать такое требование без нашего предварительного письменного согласия, если урегулирование возлагает на нас какие-либо обязательства.',
        ],
      },
      {
        title: 'Прекращение доступа',
        items: [
          '11.1. Botify вправе в любое время по собственному усмотрению, с указанием причины или без него, с предварительным уведомлением или без него: приостановить, ограничить или прекратить ваш доступ к Сервису (полностью или частично); удалить, заблокировать или ограничить ваш аккаунт, магазин, заказы или любой ваш контент; отказать в предоставлении Сервиса любому лицу.',
          '11.2. Вы можете прекратить пользоваться Сервисом в любое время.',
          '11.3. При прекращении доступа по любой причине: ваше право пользоваться Сервисом прекращается немедленно; мы можем сохранить или удалить ваши данные в соответствии с Политикой конфиденциальности и законом; мы не обязаны компенсировать утрату доступа, контента или данных.',
          '11.4. Разделы 8, 9, 10, 12 и 13 продолжают действовать после прекращения, как и любые положения, которые по своей природе подлежат сохранению.',
        ],
      },
      {
        title: 'Применимое право; обязательный индивидуальный арбитраж; отказ от групповых исков',
        items: [
          '12.1. Условия и любые споры, возникающие из них или в связи с Сервисом, регулируются материальным правом страны, в которой зарегистрирован Botify, без учёта её коллизионных норм.',
          '12.2. Сначала — неформальное урегулирование. До начала формальной процедуры вы обязуетесь добросовестно попытаться урегулировать спор с нами, связавшись через Сервис или наш канал поддержки, и дать разумное время на ответ.',
          '12.3. Обязательный индивидуальный арбитраж. В максимальной допустимой законом степени любой спор, требование или разногласие, вытекающие из Условий или связанные с Сервисом и не урегулированные неформально, подлежат разрешению исключительно путём окончательного и обязательного индивидуального арбитража по месту регистрации Botify, по применимым правилам арбитража этой юрисдикции, единоличным арбитром. Вы и Botify отказываетесь от рассмотрения таких споров судом и судом присяжных, кроме случаев, указанных в пункте 12.5.',
          '12.4. Отказ от групповых исков. В максимальной допустимой законом степени вы и Botify соглашаетесь, что требования могут предъявляться только в индивидуальном порядке и не в качестве истца или участника группы в каких-либо групповых, коллективных, консолидированных или представительных производствах. Арбитр не вправе объединять требования нескольких лиц и вести производство в групповой или представительной форме.',
          '12.5. Исключения. Индивидуальные требования, подсудные упрощённым «малым» исковым процедурам, могут быть поданы туда; любая сторона вправе обратиться в компетентный суд за временной обеспечительной мерой для пресечения фактического или угрожаемого нарушения прав интеллектуальной собственности либо другого непоправимого вреда. Ничто в этом разделе не лишает вас защиты императивных норм применимого права, которые нельзя исключить соглашением, — в той мере, в какой такие нормы к вам применимы.',
          '12.6. Делимость. Если какая-либо часть раздела 12 признана неприменимой, она отделяется, а остальная часть раздела и Условий сохраняет силу. Если признан неприменимым отказ от групповых исков, то пункты 12.3–12.4 не применяются целиком, и спор рассматривается компетентным судом в описанном выше порядке — только индивидуально.',
        ],
      },
      {
        title: 'Прочее',
        items: [
          '13.1. Делимость. Если какое-либо положение Условий признано недействительным или неприменимым, остальные положения сохраняют полную силу.',
          '13.2. Отказ от прав. Неосуществление нами какого-либо права не является отказом от него или от любого другого права.',
          '13.3. Уступка. Вы не вправе уступать свои права и обязанности. Botify вправе уступать их свободно, включая в связи со слиянием, продажей или реорганизацией, без уведомления.',
          '13.4. Форс-мажор. Botify не отвечает за задержку или неисполнение, вызванные обстоятельствами вне её разумного контроля.',
          '13.5. Полное соглашение. Условия и Политика конфиденциальности составляют полное соглашение между вами и Botify в отношении Сервиса.',
          '13.6. Контакт. Вопросы по Условиям — через наш канал поддержки или бота Botify в Telegram.',
        ],
      },
    ],
  },
  en: {
    modalTitle: 'Terms of Service',
    notice:
      'IMPORTANT — PLEASE READ CAREFULLY. These Terms of Service ("Terms") form a binding legal agreement between you and Botify ("Botify", "we", "us"). By opening or using the Botify platform — including any shop bot, web application (Mini App), storefront, chat or other feature operated on the platform (together, the "Service") — you confirm that you have read, understood and accepted these Terms, including the mandatory individual arbitration clause and the class action waiver (Section 12). These Terms apply to every user of the Service, both buyers and sellers. If you do not agree with any part of these Terms, you must immediately stop using the Service.',
    sections: [
      {
        title: 'Acceptance of Terms and Changes',
        items: [
          '1.1. By using the Service in any way you accept these Terms in full. These Terms constitute the entire agreement between you and Botify regarding the Service and supersede any prior arrangements.',
          '1.2. We may amend these Terms at any time at our sole discretion. The current version is always available in the Service. If you continue to use the Service after the amended Terms take effect, the amended Terms apply to you; if you do not agree, you must stop using the Service.',
          '1.3. These Terms are concluded in English. Any translation, including the Russian version, is provided for convenience only and has no legal force; in case of any discrepancy the English version prevails.',
        ],
      },
      {
        title: 'Eligibility and Accounts',
        items: [
          '2.1. The Service is available only to persons at least 18 years old. By using the Service you represent and warrant that you are at least 18 years old and that your use of the Service does not violate applicable law.',
          '2.2. Access to the Service requires a Telegram account. You are responsible for the security of your Telegram account and for all activity that occurs through it.',
          '2.3. You must provide accurate information where the Service requires it (for example, delivery details in an order). We are not obliged to verify it.',
        ],
      },
      {
        title: 'What Botify Is — and Is Not',
        items: [
          '3.1. Botify provides a technical platform that allows sellers to create and operate shops inside Telegram and allows buyers to browse such shops, place orders, pay and communicate with sellers.',
          '3.2. Botify is not a seller, manufacturer, importer, carrier or owner of any goods displayed in the shops. Botify does not own the shops or the goods, is not a party to any transaction between a buyer and a seller, and does not verify goods, sellers, listings or delivery.',
          '3.3. Each seller is solely responsible for their shop, its content, the goods offered, their quality and legality, delivery, refunds and compliance with applicable law. Any claims relating to a purchase must be directed to the respective seller.',
          '3.4. We may modify, suspend or discontinue any part of the Service, including any feature, at any time, without notice and without liability.',
        ],
      },
      {
        title: 'Purchases and Payments',
        items: [
          '4.1. Payments are processed by third-party payment providers. Botify does not receive, hold or process your payment credentials.',
          '4.2. Payment disputes, refunds and chargebacks are governed by the rules of the respective payment provider and, as regards goods, by the relationship between the buyer and the seller. Botify is not obliged to refund any payment.',
          '4.3. We may charge sellers fees or commission for using the Service and may change them at any time.',
        ],
      },
      {
        title: 'User Content',
        items: [
          '5.1. "User Content" is any content you submit through the Service: texts, reviews, ratings, photos, chat messages, shop names and descriptions, logos, product listings and other materials.',
          '5.2. You retain ownership of your User Content. However, you grant Botify a worldwide, royalty-free, transferable, sublicensable licence to host, store, copy, reproduce, adapt, publish, distribute, display and otherwise use the User Content solely for the purpose of operating, maintaining and developing the Service. This licence survives the end of your use of the Service to the extent necessary for backups and record-keeping.',
          '5.3. You are solely and fully responsible for all User Content you submit. Botify does not pre-moderate User Content and does not endorse it.',
          '5.4. We may, but have no obligation to, monitor, moderate, edit or remove any User Content at any time at our sole discretion, with or without notice, in particular for violations of these Terms or applicable law.',
        ],
      },
      {
        title: 'Prohibited Use',
        items: [
          '6.1. You must not use the Service to: violate any applicable law or the rights of third parties; publish or distribute unlawful, fraudulent, defamatory, obscene, hateful, discriminatory, threatening or infringing content, including content infringing copyright, trademarks or privacy rights; sell or promote prohibited goods or services; send spam or unsolicited commercial messages; distribute malware.',
          '6.2. You must not: interfere with or disrupt the Service or its infrastructure; attempt to gain unauthorised access to the Service, other accounts or systems; scrape or collect information about other users; reverse engineer the Service except as permitted by law; bypass or circumvent any limits, security measures or technical restrictions; misrepresent your identity or affiliation; use the Service on behalf of a minor.',
          '6.3. We may investigate any suspected violation and cooperate with law enforcement.',
        ],
      },
      {
        title: 'Intellectual Property',
        items: [
          '7.1. The Service, including its software, code, design, interface, texts and the Botify brand, is owned by Botify and protected by intellectual property law. All rights not expressly granted are reserved.',
          '7.2. We grant you a limited, revocable, non-exclusive, non-transferable licence to use the Service for its intended purpose in accordance with these Terms. No other rights are granted.',
          '7.3. If you send us ideas, suggestions or feedback about the Service, you grant Botify an unrestricted, perpetual right to use them without compensation or attribution.',
        ],
      },
      {
        title: 'Disclaimer of Warranties — the Service Is Provided "As Is"',
        items: [
          '8.1. THE SERVICE IS PROVIDED ON AN "AS IS" AND "AS AVAILABLE" BASIS, WITHOUT WARRANTIES OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY LAW, BOTIFY DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED OR STATUTORY, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, ACCURACY, UNINTERRUPTED OPERATION, ERROR-FREE OPERATION AND SECURITY.',
          '8.2. Botify does not warrant that the Service will be uninterrupted, timely, secure or error-free, or that defects will be corrected; that the Service or any communication with it will be free of viruses or harmful components; that data (including orders, messages, files or statistics) will not be lost, damaged or corrupted; or that any results will be achieved.',
          '8.3. The Service depends on third parties (including Telegram and payment providers) whose operation, limits and policies are beyond the control of Botify. Botify is not responsible for their actions, outages, limits or bans.',
          '8.4. Your use of the Service is at your own risk. You are solely responsible for any damage to your device or data resulting from use of the Service.',
        ],
      },
      {
        title: 'Limitation of Liability',
        items: [
          '9.1. TO THE MAXIMUM EXTENT PERMITTED BY LAW, BOTIFY WILL NOT BE LIABLE TO YOU FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY OR PUNITIVE DAMAGES, NOR FOR ANY LOSS OF PROFITS, REVENUE, GOODWILL, DATA, BUSINESS OR ANTICIPATED SAVINGS, ARISING OUT OF OR RELATED TO THESE TERMS OR THE SERVICE — EVEN IF BOTIFY HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES AND EVEN IF ANY LIMITED REMEDY FAILS OF ITS ESSENTIAL PURPOSE.',
          '9.2. TO THE MAXIMUM EXTENT PERMITTED BY LAW, BOTIFY\'S TOTAL AGGREGATE LIABILITY TO YOU FOR ALL CLAIMS ARISING OUT OF OR RELATED TO THE SERVICE OR THESE TERMS IS LIMITED TO TWENTY UNITED STATES DOLLARS (US$20). This cap covers all claims combined — regardless of their legal basis, the number of claims or events — and cannot be increased by any circumstances.',
          '9.3. The limitations in this Section and in Section 8 apply regardless of the form of action, whether in contract, tort (including negligence) or otherwise, and form an essential basis of the bargain between you and Botify.',
          '9.4. Nothing in these Terms excludes or limits liability that cannot be excluded or limited under applicable law. In such jurisdictions the exclusions and limits apply to the maximum extent the law allows.',
        ],
      },
      {
        title: 'Indemnification',
        items: [
          '10.1. You agree to defend, indemnify and hold harmless Botify, its owners, operators, employees and contractors from and against any claims, demands, actions, investigations, damages, losses, liabilities, fines, penalties, costs and expenses, including reasonable attorneys\' fees and court or arbitration costs, arising out of or related to: (a) your User Content; (b) your use of the Service; (c) your violation of these Terms, any applicable law or third-party rights; (d) your transactions and interactions with other users, including as a buyer or a seller; (e) any claim that your use of the Service caused damage to a third party, including claims of defamation, infringement or unlawful content.',
          '10.2. We reserve the right, at our own expense, to assume the exclusive defence and control of any matter subject to indemnification. You agree to cooperate with us in the defence. You may not settle any such matter without our prior written consent if the settlement imposes any obligation on us.',
        ],
      },
      {
        title: 'Termination',
        items: [
          '11.1. Botify may, at any time and at its sole discretion, with or without reason and with or without prior notice: suspend, limit or terminate your access to the Service (in whole or in part); delete, block or restrict your account, shop, orders or any of your content; and refuse to provide the Service to any person.',
          '11.2. You may stop using the Service at any time.',
          '11.3. Upon termination of your access for any reason: your right to use the Service ceases immediately; we may retain or delete your data in accordance with the Privacy Policy and applicable law; and we are not obliged to compensate the loss of access, content or data.',
          '11.4. Sections 8, 9, 10, 12 and 13 survive any termination, together with any provisions which by their nature should survive.',
        ],
      },
      {
        title: 'Governing Law; Mandatory Individual Arbitration; Class Action Waiver',
        items: [
          '12.1. These Terms and any dispute arising out of or relating to them or the Service are governed by the substantive law of the country in which Botify is established, without regard to its conflict-of-laws rules.',
          '12.2. Informal resolution first. Before starting formal proceedings, you agree to attempt in good faith to resolve the dispute with us by contacting us through the Service or our support channel and allowing a reasonable time for a response.',
          '12.3. Mandatory individual arbitration. TO THE MAXIMUM EXTENT PERMITTED BY LAW, any dispute, claim or controversy arising out of or relating to these Terms or the Service that is not resolved informally must be resolved exclusively by final and binding individual arbitration held at the place of establishment of Botify, under the applicable arbitration rules of that jurisdiction, before a single arbitrator. You and Botify each waive the right to have such disputes decided by a court or a jury, except as provided in Section 12.5.',
          '12.4. Class action waiver. TO THE MAXIMUM EXTENT PERMITTED BY LAW, you and Botify agree that claims may be brought only in an individual capacity and not as a plaintiff or class member in any class, collective, consolidated or representative proceeding. The arbitrator may not consolidate the claims of more than one person and may not preside over any form of a class or representative proceeding.',
          '12.5. Exceptions. Individual claims that qualify for a small-claims-type forum may be brought there; either party may seek temporary injunctive or other equitable relief from a competent court to prevent actual or threatened infringement of intellectual property or other irreparable harm. Nothing in this Section deprives you of the protection of mandatory rules of applicable law that cannot be waived, to the extent such rules apply to you.',
          '12.6. Severability. If any part of this Section 12 is found unenforceable, it will be severed and the remainder of this Section and these Terms will remain in force. If the class action waiver is found unenforceable, Sections 12.3–12.4 will be unenforceable in their entirety and the dispute will proceed before a competent court in the manner described above — individually only.',
        ],
      },
      {
        title: 'Miscellaneous',
        items: [
          '13.1. Severability. If any provision of these Terms is found invalid or unenforceable, the remaining provisions remain in full force.',
          '13.2. No waiver. Our failure to enforce any provision is not a waiver of that or any other provision.',
          '13.3. Assignment. You may not assign or transfer your rights or obligations. Botify may assign or transfer them freely, including in connection with a merger, sale or restructuring, without notice.',
          '13.4. Force majeure. Botify is not liable for delay or failure to perform caused by circumstances beyond its reasonable control.',
          '13.5. Entire agreement. These Terms and the Privacy Policy constitute the entire agreement between you and Botify regarding the Service.',
          '13.6. Contact. Questions about these Terms — via our support channel or the Botify bot in Telegram.',
        ],
      },
    ],
  },
}
