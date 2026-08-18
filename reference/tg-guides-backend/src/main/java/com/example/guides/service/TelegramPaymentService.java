package com.example.guides.service;

import com.example.guides.model.Guide;
import com.example.guides.model.Person;
import com.example.guides.service.GuideService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.invoices.SendInvoice;
import org.telegram.telegrambots.meta.api.objects.payments.LabeledPrice;
import org.telegram.telegrambots.meta.api.objects.payments.SuccessfulPayment;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Message;
import org.telegram.telegrambots.meta.api.objects.payments.PreCheckoutQuery;
import org.telegram.telegrambots.meta.api.methods.AnswerPreCheckoutQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.Arrays;

@Service
public class TelegramPaymentService {

    private TelegramLongPollingBot telegramBot = new TelegramLongPollingBot() {

        @Override
        public String getBotUsername() {
            return "irlguides_bot";  
        }

        @Override
        public String getBotToken() {
            return "7783867804:AAGXzVtEVTgao4HtQZlpJf8SwHAbRh7e67o";  
        }

        @Override
        public void onUpdateReceived(Update update) {
            System.out.println("Received an update: " + update.toString());

            if (update.hasPreCheckoutQuery()) {
                PreCheckoutQuery preCheckoutQuery = update.getPreCheckoutQuery();
                System.out.println("Answering PreCheckoutQuery for: " + preCheckoutQuery.getId());
                try {
                    execute(new AnswerPreCheckoutQuery(preCheckoutQuery.getId(), true));
                } catch (TelegramApiException e) {
                    e.printStackTrace();
                }
            }

            if (update.hasMessage() && update.getMessage().hasSuccessfulPayment()) {
                Message message = update.getMessage();
                System.out.println("Successful payment received for invoice: " + message.getSuccessfulPayment().getInvoicePayload());
                handleSuccessfulPayment(message);
            }
        }

    };


    @Autowired
    private GuideService guideService;

    // Метод для отправки инвойса пользователю через встроенный бот
    public void sendInvoice(Person buyer, Guide guide) {
        // Создаем инвойс для оплаты
        SendInvoice invoice = new SendInvoice();
        invoice.setChatId(buyer.getTelegramChatId()); // Telegram Chat ID покупателя
        invoice.setTitle("Покупка гайда");
        invoice.setDescription(guide.getTitle());
        invoice.setPayload("purchase-guide-" + guide.getId()); // Полезная нагрузка для идентификации покупки
        invoice.setProviderToken("test_provider_token"); // Ваш токен провайдера платежей от Telegram
        invoice.setCurrency("XTR"); // Валюта
        invoice.setPrices(Arrays.asList(new LabeledPrice("Гайд", guide.getPrice()))); // Цена в копейках
    
        // Отправляем инвойс через Telegram API
        try {
            telegramBot.execute(invoice);
    
            // Отправляем сообщение после успешной отправки инвойса
            SendMessage message = new SendMessage();
            message.setChatId(buyer.getTelegramChatId());
            message.setText("Инвойс отправлен. Ожидайте оплаты.");
            telegramBot.execute(message);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }
    

    public void handleSuccessfulPayment(Message message) {
        SuccessfulPayment successfulPayment = message.getSuccessfulPayment();
        String invoicePayload = successfulPayment.getInvoicePayload();

        // Check the payload
        if (invoicePayload.startsWith("purchase-guide-")) {
            Long guideId = Long.valueOf(invoicePayload.replace("purchase-guide-", ""));
            Long buyerId = message.getFrom().getId();

            // Complete the purchase and distribute the funds
            guideService.completePurchase(guideId, buyerId);

            try {
                SendMessage confirmationMessage = new SendMessage();
                confirmationMessage.setChatId(message.getChatId().toString());
                confirmationMessage.setText("Payment completed. Thank you for your purchase!");
                telegramBot.execute(confirmationMessage);
            } catch (TelegramApiException e) {
                System.out.println("Error sending confirmation message: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }
    
}
