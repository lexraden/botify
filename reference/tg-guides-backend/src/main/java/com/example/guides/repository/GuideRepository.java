package com.example.guides.repository;

import com.example.guides.constant.Language;
import com.example.guides.model.Guide;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface GuideRepository extends JpaRepository<Guide, Long> {

    List<Guide> findTop10ByLanguageOrderByEarningsDesc(Language language);
    List<Guide> findByNameContainingIgnoreCase(String name);
}
