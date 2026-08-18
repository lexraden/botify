package com.example.guides.util;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

@Component
public class MediaSaver2 {

    public void saveMedia(MultipartFile file, Path filePath) {
        try {
            // Проверяем, существует ли директория, если нет — создаем
            if (!Files.exists(filePath.getParent())) {
                Files.createDirectories(filePath.getParent());
            }

            // Сохраняем файл
            Files.copy(file.getInputStream(), filePath);

            System.out.println("File saved successfully: " + filePath.toString());
        } catch (IOException e) {
            throw new RuntimeException("Failed to save media file: " + filePath.toString(), e);
        }
    }
}
