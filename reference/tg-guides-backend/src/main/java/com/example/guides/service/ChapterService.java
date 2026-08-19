package com.example.guides.service;

import com.example.guides.model.Chapter;
import com.example.guides.repository.ChapterRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class ChapterService {

    private final ChapterRepository chapterRepository;

    @Autowired
    public ChapterService(ChapterRepository chapterRepository) {
        this.chapterRepository = chapterRepository;
    }

    public Optional<Chapter> findById(long id) {
        return chapterRepository.findById(id);
    }

    @Transactional
    public void save(Chapter chapter) {
        chapterRepository.save(chapter);
    }
    public void deleteAllByGuideId(Long guideId) {
        chapterRepository.deleteAllByGuideId(guideId);
    }
}
