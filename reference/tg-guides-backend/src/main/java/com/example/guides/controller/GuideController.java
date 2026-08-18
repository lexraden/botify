package com.example.guides.controller;

import com.example.guides.constant.Language;
import com.example.guides.dto.GuideDTO;
import com.example.guides.dto.ChapterDTO;

import com.example.guides.model.Chapter;
import com.example.guides.model.Guide;
import com.example.guides.model.Person;
import com.example.guides.model.PurchasedGuides;
import com.example.guides.security.JwtTokenProvider;
import com.example.guides.service.ChapterService;
import com.example.guides.service.GuideService;
import com.example.guides.service.PersonService;
import com.example.guides.service.TelegramPaymentService;

import com.example.guides.service.PurchasedGuidesService;
import com.example.guides.util.MediaSaver2; // Импорт MediaSaver
import com.fasterxml.jackson.databind.ObjectMapper; // Импорт ObjectMapper для работы с JSON
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import org.springframework.web.bind.annotation.RequestParam;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.modelmapper.ModelMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Optional;
import java.util.UUID; // Для генерации уникальных имен файлов
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.ArrayList;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/guides")
@Tag(name = "Контроллер для работы с гайдами")
@AllArgsConstructor
@CrossOrigin(origins = "*")
public class GuideController {

    private final GuideService guideService;
    private final TelegramPaymentService TelegramPaymentService;
    private final PersonService personService;
    private final PurchasedGuidesService purchasedGuidesService;
    private final JwtTokenProvider jwtTokenProvider;
    private final ChapterService chapterService;
    private final ModelMapper modelMapper;
    private final MediaSaver2 mediaSaver;


    @PostMapping("/purchase")
    @PreAuthorize("hasAnyAuthority('USER')")
    public ResponseEntity<String> initiatePurchase(
        @RequestParam("guideId") Long guideId, 
        @RequestParam("personId") Long personId) {
        System.out.println("initiatePurchase called with guideId: " + guideId + ", personId: " + personId);
        try {
            Guide guide = guideService.findById(guideId)
                .orElseThrow(() -> new RuntimeException("Guide not found"));
            Person person = personService.findById(personId)
                .orElseThrow(() -> new RuntimeException("Person not found"));
            // Comment out the external call
            TelegramPaymentService.sendInvoice(person, guide);
            return ResponseEntity.ok("Invoice sent for payment");
        } catch (RuntimeException e) {
            System.out.println("Exception in initiatePurchase: " + e.getMessage());
            return ResponseEntity.status(400).body(e.getMessage());
        }
    }






    @PostMapping("/payment-success")
    @PreAuthorize("hasAnyAuthority('USER')")
    public ResponseEntity<String> completePurchase(@RequestParam Long guideId, @RequestParam Long personId) {
        System.out.println("guideId: " + guideId + ", personId: " + personId);
        try {
            Optional<Guide> optionalGuide = guideService.findById(guideId);
            Guide guide = optionalGuide.get();

            // Проверяем и инициализируем weeklyEarnings, если оно null
            if (guide.getWeeklyEarnings() == null) {
                guide.setWeeklyEarnings(0);
            }

            guideService.completePurchase(guideId, personId);

            // Удаляем вызов setNewEarnings, так как earnings уже обновлены в completePurchase
            guideService.save(guide);
            return ResponseEntity.ok("Guide purchased successfully");
        } catch (RuntimeException e) {
            e.printStackTrace();
            return ResponseEntity.status(400).body("Error: " + e.getMessage());
        }
    }



    @GetMapping
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Посмотреть топ 10 гайдов по заработку")
    public List<GuideDTO> findTopGuides(@Parameter(name = "Язык гайда") @RequestParam String lang) {
        return guideService.findTopGuidesByEarnings(Language.valueOf(lang.toUpperCase()))
                .stream().map(this::fromGuide)
                .collect(Collectors.toList());
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Посмотреть гайд по идентификатору")
    public GuideDTO findById(@Parameter(name = "Идентификатор гайда") @PathVariable long id) {
        Optional<Guide> optionalGuide = guideService.findById(id);
        if (optionalGuide.isEmpty()) {
            return null;
        }
        return fromGuide(optionalGuide.get());
    }
    @GetMapping("/search")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Поиск гайдов по названию")
    public ResponseEntity<List<GuideDTO>> searchGuidesByName(
            @Parameter(name = "Название гайда") @RequestParam String name) {
        List<Guide> guides = guideService.searchByName(name);
        if (guides.isEmpty()) {
            return new ResponseEntity<>(HttpStatus.NO_CONTENT);
        }
        List<GuideDTO> guideDTOs = guides.stream()
                .map(this::fromGuide)
                .collect(Collectors.toList());
        return new ResponseEntity<>(guideDTOs, HttpStatus.OK);
    }

    @GetMapping("/{id}/purchase")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Приобрести гайд")
    public ResponseEntity<?> purchaseGuide(@Parameter(name = "Идентификатор гайда") @PathVariable long id,
                                           @Parameter(name = "Токен пользователя") @RequestHeader(HttpHeaders.AUTHORIZATION) String token) {
        Optional<Guide> optionalGuide = guideService.findById(id);
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalGuide.isEmpty()) {
            return new ResponseEntity<>("Guide not found", HttpStatus.BAD_REQUEST);
        } else if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        Guide guide = optionalGuide.get();
        Person person = optionalPerson.get();
        if (isPersonOwnsGuide(person, guide)) {
            return new ResponseEntity<>("This guide belongs to you", HttpStatus.BAD_REQUEST);
        } else if (isGuideAlreadyPurchased(person, guide)) {
            return new ResponseEntity<>("This guide already purchased", HttpStatus.BAD_REQUEST);
        }
        setNewEarnings(guide);
        saveNewPurchasedGuide(person, guide);
        guideService.save(guide);
        return new ResponseEntity<>("OK", HttpStatus.OK);
    }
    @GetMapping("/all")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить все гайды")
    public List<GuideDTO> findAllGuides() {
        List<Guide> guides = guideService.findAll();
        return guides.stream()
                .map(this::fromGuide)
                .collect(Collectors.toList());
    }
    @PostMapping("/create")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Создать гайд")
    public ResponseEntity<?> createGuide(
            @RequestHeader(HttpHeaders.AUTHORIZATION) String token,
            @RequestParam("mainImg") MultipartFile mainImg,
            @RequestParam("guideData") String guideData,
            @RequestParam("chapters") String chaptersData, // Теперь это будет массив строк JSON с данными глав
            @RequestParam(value = "chapterImages", required = false) List<MultipartFile> chapterImages,
            @RequestParam(value = "chapterVideos", required = false) List<MultipartFile> chapterVideos) {

        try {
            if (guideData == null || guideData.isEmpty()) {
                return new ResponseEntity<>("guideData is missing", HttpStatus.BAD_REQUEST);
            }

            // Получаем автора через токен
            Optional<Person> optionalPerson = getPersonByToken(token);
            if (optionalPerson.isEmpty()) {
                return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
            }
            Person author = optionalPerson.get();

            // Преобразуем строку JSON в GuideDTO
            ObjectMapper mapper = new ObjectMapper();
            GuideDTO guideDTO = mapper.readValue(guideData, GuideDTO.class);

            // Преобразуем GuideDTO в Guide
            Guide guide = toGuide(guideDTO, author);
            guide.setAuthor(author);

            // Сохраняем изображение для гайда
            String mainImgName = saveMediaFile(mainImg, "guide", guide.getId());
            if (mainImgName != null) {
                guide.setMainImg(mainImgName);  // Сохраняем имя файла в базу данных
            }

            // Преобразуем строку JSON с данными глав в List<ChapterDTO>
            List<ChapterDTO> chapterDTOList = mapper.readValue(chaptersData,
                mapper.getTypeFactory().constructCollectionType(List.class, ChapterDTO.class));

            // Обрабатываем и сохраняем каждую главу
            for (int i = 0; i < chapterDTOList.size(); i++) {
                ChapterDTO chapterDTO = chapterDTOList.get(i);
                Chapter chapter = new Chapter();
                chapter.setName(chapterDTO.getName());
                chapter.setText(chapterDTO.getText());
                chapter.setGuide(guide);

                if (chapterImages != null && chapterImages.size() > i) {
                    String chapterImgName = saveMediaFile(chapterImages.get(i), "chapter/image", chapter.getId());
                    if (chapterImgName != null) {
                        chapter.setImg(chapterImgName);
                    }
                }
                if (chapterVideos != null && chapterVideos.size() > i) {
                    String chapterVideoName = saveMediaFile(chapterVideos.get(i), "chapter/video", chapter.getId());
                    if (chapterVideoName != null) {
                        chapter.setVideo(chapterVideoName);
                    }
                }
                guide.getChapters().add(chapter);
            }

            // Сохраняем гайд в базе данных
            guideService.save(guide);

            return new ResponseEntity<>(guide.getId(), HttpStatus.OK);

        } catch (Exception e) {
            return new ResponseEntity<>("Error creating guide: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }



    @DeleteMapping("/delete/{id}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Удалить гайд")
    public ResponseEntity<?> deleteGuide(
            @PathVariable Long id,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String token) {
        try {
            Optional<Person> optionalPerson = getPersonByToken(token);
            if (optionalPerson.isEmpty()) {
                return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
            }
            Person author = optionalPerson.get();
    
            Optional<Guide> optionalGuide = guideService.findById(id);
            if (optionalGuide.isEmpty()) {
                return new ResponseEntity<>("Guide not found", HttpStatus.NOT_FOUND);
            }
            Guide guide = optionalGuide.get();
    
            if (!guide.getAuthor().equals(author)) {
                return new ResponseEntity<>("You are not the author of this guide", HttpStatus.FORBIDDEN);
            }
    
            // Удаление связанных записей из purchased_guides
            purchasedGuidesService.deleteByGuideId(id);
    
            // Удаление медиафайлов
            if (guide.getMainImg() != null) {
                deleteMediaFile("static/guide/" + guide.getMainImg());
            }
            for (Chapter chapter : guide.getChapters()) {
                if (chapter.getImg() != null) {
                    deleteMediaFile("static/chapter/image/" + chapter.getImg());
                }
                if (chapter.getVideo() != null) {
                    deleteMediaFile("static/chapter/video/" + chapter.getVideo());
                }
            }
    
            // Удаление гайда
            guideService.deleteById(id);
    
            return new ResponseEntity<>("Guide deleted successfully", HttpStatus.OK);
        } catch (Exception e) {
            e.printStackTrace();
            return new ResponseEntity<>("Error deleting guide: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }
    
    @PutMapping("/update/{id}")
@PreAuthorize("hasAnyAuthority('USER')")
@Operation(summary = "Изменить гайд")
public ResponseEntity<?> updateGuide(
        @PathVariable Long id,
        @RequestHeader(HttpHeaders.AUTHORIZATION) String token,
        @RequestParam("guideData") String guideData,
        @RequestParam("chapters") String chaptersData,
        @RequestParam(value = "mainImg", required = false) MultipartFile mainImg,
        @RequestParam(value = "chapterImages", required = false) List<MultipartFile> chapterImages,
        @RequestParam(value = "chapterVideos", required = false) List<MultipartFile> chapterVideos) {

    try {
        System.out.println("Incoming Guide Data: " + guideData);
        System.out.println("Incoming Chapters Data: " + chaptersData);
        if (chapterImages != null) {
            System.out.println("Incoming Chapter Images: " + chapterImages.size());
        } else {
            System.out.println("No Chapter Images received.");
        }
        
        if (chapterVideos != null) {
            System.out.println("Incoming Chapter Videos: " + chapterVideos.size());
        } else {
            System.out.println("No Chapter Videos received.");
        }
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        Person author = optionalPerson.get();

        // Проверка существования гайда
        Optional<Guide> optionalGuide = guideService.findById(id);
        if (optionalGuide.isEmpty()) {
            return new ResponseEntity<>("Guide not found", HttpStatus.NOT_FOUND);
        }
        Guide guide = optionalGuide.get();

        // Проверка авторства
        if (!guide.getAuthor().equals(author)) {
            return new ResponseEntity<>("You are not the author of this guide", HttpStatus.FORBIDDEN);
        }

        // Обновление данных гайда
        ObjectMapper mapper = new ObjectMapper();
        GuideDTO guideDTO = mapper.readValue(guideData, GuideDTO.class);
        guide.setName(guideDTO.getName());
        guide.setDescription(guideDTO.getDescription());
        guide.setPrice(guideDTO.getPrice());

        // Обновление глав
        List<ChapterDTO> chapterDTOList = mapper.readValue(chaptersData,
                mapper.getTypeFactory().constructCollectionType(List.class, ChapterDTO.class));

        // Создаем карту существующих глав по ID
        Map<Long, Chapter> existingChapterMap = guide.getChapters().stream()
                .collect(Collectors.toMap(Chapter::getId, chapter -> chapter));

        // Создаем список обновленных глав
        List<Chapter> updatedChapters = new ArrayList<>();

        for (int i = 0; i < chapterDTOList.size(); i++) {
            ChapterDTO chapterDTO = chapterDTOList.get(i);
            Chapter chapter;

            if (chapterDTO.getId() != null && existingChapterMap.containsKey(chapterDTO.getId())) {
                // Обновляем существующую главу
                chapter = existingChapterMap.get(chapterDTO.getId());
            } else {
                // Создаем новую главу
                chapter = new Chapter();
                chapter.setGuide(guide);
            }

            // Обновляем данные главы
            chapter.setName(chapterDTO.getName());
            chapter.setText(chapterDTO.getText());

            // Обновляем изображение главы
            if (chapterImages != null && chapterImages.size() > i && !chapterImages.get(i).isEmpty()) {
                String chapterImgName = saveMediaFile(chapterImages.get(i), "chapter/image", chapter.getId());
                chapter.setImg(chapterImgName);
            }

            // Обновляем видео главы
            if (chapterVideos != null && chapterVideos.size() > i && !chapterVideos.get(i).isEmpty()) {
                String chapterVideoName = saveMediaFile(chapterVideos.get(i), "chapter/video", chapter.getId());
                chapter.setVideo(chapterVideoName);
            }

            // Добавляем главу в список обновленных
            updatedChapters.add(chapter);
        }

        // Обновляем коллекцию глав в объекте Guide
        guide.getChapters().clear();
        guide.getChapters().addAll(updatedChapters);

        // Обновляем изображение гайда
        if (mainImg != null && !mainImg.isEmpty()) {
            String mainImgName = saveMediaFile(mainImg, "guide", guide.getId());
            guide.setMainImg(mainImgName);
        }

        // Сохраняем обновленный гайд
        guideService.save(guide);

        return new ResponseEntity<>("Guide updated successfully", HttpStatus.OK);

    } catch (Exception e) {
        e.printStackTrace();
        return new ResponseEntity<>("Error updating guide: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
    }
}
    





    private String saveMediaFile(MultipartFile file, String folder, Long entityId) throws Exception {
    if (file != null && !file.isEmpty()) {
        String fileName = UUID.randomUUID().toString() + "_" + file.getOriginalFilename();
        Path filePath = Path.of("static/" + folder + "/", fileName);  // Изменено на static/

        Files.createDirectories(filePath.getParent());  // Убедитесь, что директория существует
        mediaSaver.saveMedia(file, filePath);
        System.out.println("File saved: " + filePath.toString());
        return fileName;
    } else {
        System.out.println("File is null or empty.");
        return null;
    }
}


    private void defineLanguage(Guide guide) {
        StringBuilder builder = new StringBuilder();
        builder.append(guide.getDescription());
        for (Chapter chapter : guide.getChapters()) {
            builder.append(chapter.getText());
        }
        String fullText = builder.toString();
        guide.setLanguage(countSymbols(fullText));
    }

    private Language countSymbols(String fullText) {
        Pattern russianPattern = Pattern.compile("[а-яА-ЯёЁ]");
        Matcher russianMatcher = russianPattern.matcher(fullText);
        Pattern englishPattern = Pattern.compile("[a-zA-Z]");
        Matcher englishMatcher = englishPattern.matcher(fullText);
        int russianCount = 0;
        while (russianMatcher.find()) {
            russianCount++;
        }
        int englishCount = 0;
        while (englishMatcher.find()) {
            englishCount++;
        }
        float totalCount = russianCount + englishCount;
        boolean twentyPercentsOfFullText = totalCount / 5 <= russianCount;
        if (twentyPercentsOfFullText) {
            return Language.RU;
        }
        return Language.ENG;
    }




    private String generateUniqueFileName(String originalFileName) {
        String extension = originalFileName.substring(originalFileName.lastIndexOf("."));
        return UUID.randomUUID().toString() + "_" + System.currentTimeMillis() + extension;
    }

    private void setNewEarnings(Guide guide) {
        int newCount = guide.getCount() + 1;
        guide.setCount(newCount);
        guide.setEarnings(newCount * guide.getPrice());
    }

    private void saveChapters(Guide guide, List<Chapter> chapters) {
        for (Chapter chapter : chapters) {
            chapter.setGuide(guide);
            chapterService.save(chapter);
        }
    }

    private boolean isGuideAlreadyPurchased(Person person, Guide guide) {
        long count = person.getPurchasedGuides().stream().map(PurchasedGuides::getGuide)
                .filter(e -> e.equals(guide))
                .count();
        return count == 1;
    }

    private boolean isPersonOwnsGuide(Person person, Guide guide) {
        return guide.getAuthor() == person;
    }

    private Optional<Person> getPersonByToken(String token) {
        String username = jwtTokenProvider.getUsername(token);
        return personService.findByUsername(username);
    }

    private void saveNewPurchasedGuide(Person person, Guide guide) {
        PurchasedGuides purchasedGuides = new PurchasedGuides(person, guide);
        purchasedGuidesService.save(purchasedGuides);
    }

    private Guide toGuide(GuideDTO guideDTO, Person author) {
        Guide guide = modelMapper.map(guideDTO, Guide.class);
        guide.setAuthor(author);
        
        // Ensure chapters list is initialized
        if (guide.getChapters() == null) {
            guide.setChapters(new ArrayList<>());
        }
        
        return guide;
    }

    private GuideDTO fromGuide(Guide guide) {
        GuideDTO guideDTO = modelMapper.map(guide, GuideDTO.class);
        guideDTO.setAuthor(guide.getAuthor().getUsername());  // Передаем username вместо ID
        return guideDTO;
    }
    private void deleteMediaFile(String filePath) {
    try {
        Path path = Path.of(filePath);
        if (Files.exists(path)) {
            Files.delete(path);
            System.out.println("File deleted: " + filePath);
        }
    } catch (Exception e) {
        System.out.println("Error deleting file: " + e.getMessage());
    }
}
}
