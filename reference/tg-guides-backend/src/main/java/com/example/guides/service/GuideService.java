package com.example.guides.service;

import com.example.guides.constant.Language;
import com.example.guides.model.Guide;
import com.example.guides.model.Person;
import com.example.guides.model.PurchasedGuides;

import com.example.guides.repository.GuideRepository;
import com.example.guides.repository.PurchasedGuidesRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.example.guides.model.Referral;
import org.springframework.scheduling.annotation.Scheduled;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Service
public class GuideService {

    private final GuideRepository guideRepository;
    @Autowired
    private PersonService personService;

    @Autowired
    private PurchasedGuidesRepository purchasedGuidesRepository;
    @Autowired
    public GuideService(GuideRepository guideRepository) {
        this.guideRepository = guideRepository;
    }

    public List<Guide> findTopGuidesByEarnings(Language language) {
        return guideRepository.findTop10ByLanguageOrderByEarningsDesc(language);
    }

    public Optional<Guide> findById(long id) {
        return guideRepository.findById(id);
    }
    public List<Guide> findAll() {
        return guideRepository.findAll();
    }

    public void completePurchase(Long guideId, Long personId) {
        Guide guide = guideRepository.findById(guideId).orElseThrow(() -> new RuntimeException("Guide not found"));
        Person buyer = personService.findById(personId).orElseThrow(() -> new RuntimeException("Buyer not found"));
        Person author = guide.getAuthor();
        
        // Обновляем баланс автора
        personService.updateBalance(author.getId(), guide.getPrice());
        
        // Если у автора есть рефералы, выплачиваем бонусы рефералам
        if (author.getReferredBy() != null) {
            int referralPercentage = 10;  // Процент бонуса рефералам
            long referralBonus = guide.getPrice() * referralPercentage / 100;
        
            // Начисляем бонусы всем рефералам
            for (Referral referrer : author.getReferredBy()) {
                Long referrerId = referrer.getReferralOwner().getId();
                personService.updateBalance(referrerId, referralBonus);
            }
        }
        
        // Создаем запись о покупке
        PurchasedGuides purchasedGuide = new PurchasedGuides();
        purchasedGuide.setGuide(guide);
        purchasedGuide.setPerson(buyer);
        purchasedGuidesRepository.save(purchasedGuide);
        
        // Обновляем количество покупок и общие заработки
        guide.setCount(guide.getCount() + 1);  // Увеличиваем только на 1
        guide.setEarnings(guide.getEarnings() + guide.getPrice());  // Увеличиваем earnings на price
        
        // Обновляем недельные заработки
        if (guide.getWeeklyEarnings() == null) {
            guide.setWeeklyEarnings(0);  // Инициализация, если null
        }
        guide.setWeeklyEarnings(guide.getWeeklyEarnings() + guide.getPrice());  // Увеличиваем на price
        
        // Сохраняем изменения в гиде
        guideRepository.save(guide);
    }
    
    


    @Transactional
    public void save(Guide guide) {
        guide.setCreatedAt(LocalDateTime.now());
        guideRepository.save(guide);
    }
    public List<Guide> searchByName(String name) {
        return guideRepository.findByNameContainingIgnoreCase(name);
    }
    public int getWeeklyEarnings(Guide guide) {
        LocalDateTime oneWeekAgo = LocalDateTime.now().minusDays(7);
        Integer sum = purchasedGuidesRepository.sumEarningsByGuideAndPurchaseDateAfter(guide, oneWeekAgo);
        return sum != null ? sum : 0;
    }
    @Scheduled(cron = "0 0 0 * * SUN") 
    public void resetWeeklyEarnings() {
        List<Guide> guides = guideRepository.findAll();
        for (Guide guide : guides) {
            guide.setWeeklyEarnings(0);
            guideRepository.save(guide);
        }
    }
    public void deleteById(Long id) {
        guideRepository.deleteById(id);
    }
}
