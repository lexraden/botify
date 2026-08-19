package com.example.guides.util;

import com.example.guides.constant.FilesFormat;
import com.example.guides.model.Person;
import com.example.guides.dto.ChapterDTO;
import com.example.guides.dto.GuideDTO;
import com.example.guides.dto.PersonDTO;
import org.apache.tomcat.util.http.fileupload.IOUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import net.coobird.thumbnailator.Thumbnails;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;

@Component
public class MediaSaver {

    @Value("${upload.profile.path}")
    private String profilePath;

    public boolean saveProfilePhoto(MultipartFile file, Person person) {
    try {
        Path directory = Path.of(profilePath);
        if (!Files.exists(directory)) {
            Files.createDirectories(directory);
        }

        String fileName = String.format("%s/%s.%s", profilePath, person.getUsername(), FilesFormat.IMAGE.getFormat());
        System.out.println("Сохранение файла: " + fileName);
        Path filePath = Path.of(fileName);

        boolean isSaved = saveMedia(file, filePath);
        if (isSaved) {
            System.out.println("Фото профиля успешно сохранено.");
        }
        return isSaved;
    } catch (IOException e) {
        throw new RuntimeException("Failed to save profile photo", e);
    }
}


    public boolean saveMedia(MultipartFile file, Path filePath) {
    try (InputStream inputStream = file.getInputStream()) {
        Thumbnails.of(inputStream)
          .size(200, 200) 
          .outputFormat("jpg")
          .toFile(filePath.toFile());
    } catch (IOException e) {
        throw new RuntimeException("Failed to read or convert image", e);
    }
    return true;
}

}
