package com.example.guides.repository;

import com.example.guides.model.Chapter;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ChapterRepository extends JpaRepository<Chapter, Long> {
    void deleteAllByGuideId(Long guideId);

}
