// Текст условий использования: небольшой, поэтому живёт рядом с кодом и
// бандлится вместе с приложением — модалке не нужен сетевой запрос.
// Юридические формулировки правятся только согласованно с владельцем проекта.

export const TERMS = {
  ru: {
    // Дисклеймер разбит на части, чтобы ссылка была внутри предложения
    agreeBefore: 'Продолжая, ты принимаешь наши ',
    agreeLink: 'условия использования',
    agreeAfter: '.',
    modalTitle: 'Условия использования',
    sections: [
      {
        title: '1. О платформе',
        body:
          'Botify — онлайн-платформа, с помощью которой продавцы создают магазины ' +
          'внутри Telegram и продают товары и услуги. Платформа предоставляет ' +
          'технический инструмент: витрину, каталог, приём оплат через сторонние ' +
          'платёжные сервисы, заказы и рассылки. Botify не является владельцем ' +
          'магазинов и не участвует в сделках между продавцом и покупателем.',
      },
      {
        title: '2. Ответственность продавца',
        body:
          'Продавец единолично отвечает за всё, что размещает и продаёт через свой ' +
          'магазин: за достоверность описаний, качество и фактическое предоставление ' +
          'товара или услуги, сроки, возвраты и споры с покупателями. Все ' +
          'обязательства перед покупателем исполняет продавец.',
      },
      {
        title: '3. Границы ответственности платформы',
        body:
          'Botify не проверяет товары и не контролирует их фактическое предоставление, ' +
          'поэтому не отвечает за содержание, законность, качество и исполнение товаров ' +
          'и услуг конкретного продавца. При этом платформа отвечает за собственную ' +
          'работу: Botify выполняет свои обязательства перед продавцом в объёме и на ' +
          'условиях, установленных применимым законодательством.',
      },
      {
        title: '4. Комплаенс',
        body:
          'Продавец самостоятельно соблюдает применимое законодательство и правила ' +
          'сторонних сервисов — Telegram, платёжных провайдеров и других. Продавать ' +
          'товары и услуги, оборот которых ограничен или запрещён, нельзя: нарушение ' +
          'может привести к отключению магазина.',
      },
      {
        title: '5. Комиссии',
        body:
          'Botify удерживает комиссию 5% с суммы продажи. Платёжные провайдеры ' +
          '(например, Crypto Pay) могут дополнительно удерживать собственные ' +
          'комиссии — они устанавливаются провайдером и от платформы не зависят.',
      },
      {
        title: '6. Сторонние сервисы',
        body:
          'Магазин работает поверх независимых сервисов: Telegram и платёжных систем. ' +
          'Их сбои, лимиты и блокировки находятся вне контроля платформы. Botify не ' +
          'отвечает за действия сторонних сервисов, но помогает продавцу разобраться ' +
          'в возникшей проблеме в разумных пределах.',
      },
      {
        title: '7. Общие положения',
        body:
          'Совокупная ответственность Botify перед продавцом ограничена суммой ' +
          'комиссии, удержанной платформой с его продаж за последние 3 месяца. ' +
          'Условия могут меняться: о существенных изменениях платформа предупреждает ' +
          'заранее в боте или приложении. Эти условия применяются к работе продавца ' +
          'в Botify.',
      },
    ],
  },
  en: {
    agreeBefore: 'By continuing, you agree to our ',
    agreeLink: 'Terms and Conditions',
    agreeAfter: '.',
    modalTitle: 'Terms and Conditions',
    sections: [
      {
        title: '1. About the platform',
        body:
          'Botify is an online platform that lets sellers run shops inside Telegram ' +
          'and sell goods and services. The platform provides the tooling: a ' +
          'storefront, catalog, payments via third-party providers, orders and ' +
          'mailings. Botify does not own the shops and is not a party to any deal ' +
          'between a seller and a buyer.',
      },
      {
        title: '2. Seller responsibility',
        body:
          'The seller is solely responsible for everything they list and sell through ' +
          'their shop: the accuracy of descriptions, the quality and actual delivery ' +
          'of goods or services, timing, refunds and buyer disputes. All obligations ' +
          'towards the buyer are fulfilled by the seller.',
      },
      {
        title: '3. Limits of platform liability',
        body:
          'Botify does not review goods or control their actual delivery, and is ' +
          'therefore not liable for the content, legality, quality or fulfilment of ' +
          "any seller's goods or services. At the same time, the platform stands " +
          'behind its own operation: Botify fulfils its obligations to the seller to ' +
          'the extent established by applicable law.',
      },
      {
        title: '4. Compliance',
        body:
          'The seller is solely responsible for complying with applicable law and the ' +
          'rules of third-party services — Telegram, payment providers and others. ' +
          'Selling restricted or prohibited goods or services is not allowed; ' +
          'violations may lead to shop suspension.',
      },
      {
        title: '5. Fees',
        body:
          'Botify charges a 5% commission on sales. Payment providers (e.g. Crypto ' +
          'Pay) may additionally charge their own fees; those are set by the provider ' +
          "and are outside the platform's control.",
      },
      {
        title: '6. Third-party services',
        body:
          'Shops run on top of independent services: Telegram and payment systems. ' +
          "Their outages, limits and bans are beyond the platform's control. Botify " +
          "is not liable for third-party actions, but helps the seller resolve " +
          'issues where reasonably possible.',
      },
      {
        title: '7. General provisions',
        body:
          "Botify's aggregate liability to a seller is limited to the commission " +
          "retained by the platform from that seller's sales over the last 3 months. " +
          'These terms may change: the platform gives advance notice of material ' +
          'changes in the bot or the app. These terms govern the seller’s work ' +
          'with Botify.',
      },
    ],
  },
}
