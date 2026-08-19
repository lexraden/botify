package com.example.guides.service;

import com.example.guides.model.PurchasedGuides;
import com.example.guides.repository.PurchasedGuidesRepository;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@AllArgsConstructor
public class PurchasedGuidesService {

    private final PurchasedGuidesRepository purchasedGuidesRepository;

    @Transactional
    public void save(PurchasedGuides purchasedGuides) {
        purchasedGuidesRepository.save(purchasedGuides);
    }
    @Transactional
    public void deleteByGuideId(Long guideId) {
        purchasedGuidesRepository.deleteByGuideId(guideId);
    }

}
