package com.example.guides.repository;

import com.example.guides.model.Guide;
import com.example.guides.model.PurchasedGuides;

import java.time.LocalDateTime;
import org.springframework.data.jpa.repository.Modifying;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
@Repository
public interface PurchasedGuidesRepository extends JpaRepository<PurchasedGuides, Long> {
    @Query("SELECT SUM(pg.purchasePrice) FROM PurchasedGuides pg WHERE pg.guide = :guide AND pg.purchaseDate >= :startDate")
    Integer sumEarningsByGuideAndPurchaseDateAfter(@Param("guide") Guide guide, @Param("startDate") LocalDateTime startDate);


    @Modifying
    @Query("DELETE FROM PurchasedGuides pg WHERE pg.guide.id = :guideId")
    void deleteByGuideId(@Param("guideId") Long guideId);
}
