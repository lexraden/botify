package com.example.guides.controller;

import com.example.guides.dto.ChapterDTO;
import com.example.guides.dto.GuideDTO;
import com.example.guides.dto.PersonDTO;
import com.example.guides.dto.ReferralDTO;
import com.example.guides.model.Chapter;
import com.example.guides.model.Guide;
import com.example.guides.model.Person;
import com.example.guides.model.PurchasedGuides;
import com.example.guides.security.JwtTokenProvider;
import com.example.guides.service.ChapterService;
import com.example.guides.service.GuideService;
import com.example.guides.service.PersonService;
import com.example.guides.util.MediaSaver;
import com.example.guides.constant.FilesFormat;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.modelmapper.ModelMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.hibernate.Hibernate;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;
import javax.annotation.PostConstruct;

@RestController
@RequestMapping("/api/v1/user-profile")
@Tag(name = "Контроллер для работы с профилем пользователя")
@AllArgsConstructor
@CrossOrigin(origins = "*")
public class ProfileController {

    private final PersonService personService;
    private final GuideService guideService;
    private final ChapterService chapterService;
    private final ModelMapper modelMapper;
    private final JwtTokenProvider jwtTokenProvider;
    private final MediaSaver mediaSaver;

    @PostConstruct
    public void init() {
        // Настройка ModelMapper для преобразования Person в long id
        modelMapper.typeMap(Guide.class, GuideDTO.class)
            .addMappings(mapper -> mapper.map(src -> src.getAuthor().getId(), GuideDTO::setAuthor));
    }

    @PatchMapping
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Изменить информация о пользователе")
    public ResponseEntity<?> changePersonInformation(@Parameter(name = "Измененные объект пользователя")
                                                        @RequestBody PersonDTO personDTO) {
        Optional<Person> optionalPerson = personService.findById(personDTO.getId());
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        Person person = optionalPerson.get();
        if (personDTO.getDescription() != null) {
            person.setDescription(personDTO.getDescription());
            personService.save(person);
        }
        return new ResponseEntity<>("Data has changed!", HttpStatus.OK);
    }

     @GetMapping
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить информацию о пользователе")
    public PersonDTO getPersonInformation(@Parameter(name = "Токен пользователя")
                                            @RequestHeader(HttpHeaders.AUTHORIZATION)
                                          String token) {
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return null;
        }
        return fromPerson(optionalPerson.get());
    }

     @GetMapping("/guides")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить все гайды пользователя либо купленные")
    public ResponseEntity<?> getGuides(@RequestHeader(HttpHeaders.AUTHORIZATION) String token,
                                    @RequestParam boolean own) {
        try {
            Optional<Person> optionalPerson = getPersonByToken(token);
            if (optionalPerson.isEmpty()) {
                return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
            }
            Person person = optionalPerson.get();
            List<Guide> result = (own) ? person.getGuides() : person.getPurchasedGuides()
                                            .stream().map(PurchasedGuides::getGuide)
                                            .collect(Collectors.toList());

            if (result == null || result.isEmpty()) {
                return new ResponseEntity<>(HttpStatus.NO_CONTENT);
            }
            List<GuideDTO> guideDTOs = result.stream().map(this::fromGuide).collect(Collectors.toList());
            return new ResponseEntity<>(guideDTOs, HttpStatus.OK);
        } catch (Exception e) {
            e.printStackTrace();
            return new ResponseEntity<>("Internal server error: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }


    @GetMapping("/guides/{id}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить гайд по идентификатору")
    public ResponseEntity<?> getGuideById(@Parameter(name = "Идентификатор гайда") @PathVariable long id,
                                        @RequestHeader(HttpHeaders.AUTHORIZATION) String token) {
        Optional<Guide> optionalGuide = guideService.findById(id);
        Optional<Person> optionalPerson = getPersonByToken(token);

        if (optionalGuide.isEmpty()) {
            return new ResponseEntity<>("Guide not found", HttpStatus.BAD_REQUEST);
        }

        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }

        Guide guide = optionalGuide.get();
        Person person = optionalPerson.get();

        // Check if the user is the author or has purchased the guide
        boolean isOwnerOrPurchased = Objects.equals(guide.getAuthor().getId(), person.getId()) ||
            person.getPurchasedGuides().stream()
                .anyMatch(purchasedGuide -> Objects.equals(purchasedGuide.getGuide().getId(), id)
                );

        // If the user is neither the owner nor the purchaser, clear the chapters
        GuideDTO guideDTO = fromGuide(guide);
        if (!isOwnerOrPurchased) {
            guideDTO.setChapters(new ArrayList<>());
        }

        // Adding paths for images and videos as usual
        if (guide.getMainImg() != null) {
            guide.setMainImg(guide.getMainImg());
        }

        guide.getChapters().forEach(chapter -> {
            if (chapter.getImg() != null) {
                chapter.setImg(chapter.getImg());
            }
            if (chapter.getVideo() != null) {
                chapter.setVideo(chapter.getVideo());
            }
        });

        return new ResponseEntity<>(guideDTO, HttpStatus.OK);
    }


    @PatchMapping("/guides/{id}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Изменить гайд по идентификатору")
    public ResponseEntity<?> updateGuideById(@Parameter(name = "Идентификатор гайда")
                                             @PathVariable long id,
                                             @Parameter(name = "Измененный гайд")
                                             @RequestBody GuideDTO guideDTO) {
        Optional<Guide> optionalGuide = guideService.findById(id);
        if (optionalGuide.isEmpty()) {
            return new ResponseEntity<>("Guide not found", HttpStatus.BAD_REQUEST);
        }
        Guide guide = optionalGuide.get();
        updateGuide(guide, guideDTO);
        guideService.save(guide);
        return new ResponseEntity<>("Ok", HttpStatus.OK);
    }

    @GetMapping("/profile/username/{username}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить информацию о пользователе по имени пользователя")
    public ResponseEntity<?> getUserProfileByUsername(
            @Parameter(name = "Имя пользователя") 
            @PathVariable String username) {
        try {
            Optional<Person> optionalPerson = personService.findByUsername(username);
            if (optionalPerson.isEmpty()) {
                return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
            }
            
            // Конвертируем найденного пользователя в DTO
            PersonDTO personDTO = fromPerson(optionalPerson.get());
            String imageUrl = String.format("/uploads/profiles/%s.%s", optionalPerson.get().getUsername(), FilesFormat.IMAGE.getFormat());
            personDTO.setImageUrl(imageUrl);  
            return ResponseEntity.ok(personDTO);
        } catch (Exception e) {
            e.printStackTrace();
            return new ResponseEntity<>("Internal server error: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    @GetMapping("/guides/username/{username}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить гайды пользователя по имени пользователя")
    public ResponseEntity<?> getGuidesByUsername(
            @Parameter(name = "Имя пользователя") 
            @PathVariable String username) {
        try {
            // Ищем пользователя по имени пользователя
            Optional<Person> optionalPerson = personService.findByUsername(username);
            if (optionalPerson.isEmpty()) {
                return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
            }
            Person person = optionalPerson.get();

            // Получаем гайды пользователя
            List<Guide> guides = person.getGuides();
            if (guides == null || guides.isEmpty()) {
                return new ResponseEntity<>(HttpStatus.NO_CONTENT);
            }

            // Преобразуем список гайдов в DTO
            List<GuideDTO> guideDTOs = guides.stream().map(this::fromGuide).collect(Collectors.toList());
            return new ResponseEntity<>(guideDTOs, HttpStatus.OK);
        } catch (Exception e) {
            e.printStackTrace();
            return new ResponseEntity<>("Internal server error: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }


    @GetMapping("/guides/{guideId}/chapters/{chapterId}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить главу гайда по его идентификатору")
    public ChapterDTO getChapterById(@Parameter(name = "Идентификатор главы")
                                     @PathVariable long chapterId) {
        Optional<Chapter> optionalChapter = chapterService.findById(chapterId);
        if (optionalChapter.isEmpty()) {
            return null;
        }
        return fromChapter(optionalChapter.get());
    }

    @PatchMapping("/guides/{guideId}/chapters/{chapterId}")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Изменить главу гайда")
    public ResponseEntity<?> updateChapterById(@Parameter(name = "Идентификатор главы")
                                           @PathVariable long chapterId,
                                               @Parameter(name = "Изменная глава")
                                               @RequestBody ChapterDTO chapterDTO) {
        Optional<Chapter> optionalChapter = chapterService.findById(chapterId);
        if (optionalChapter.isEmpty()) {
            return new ResponseEntity<>("Chapter not found", HttpStatus.BAD_REQUEST);
        }
        Chapter chapter = optionalChapter.get();
        updateChapter(chapter, chapterDTO);
        chapterService.save(chapter);
        return new ResponseEntity<>("Ok", HttpStatus.OK);
    }

    @PostMapping("/upload-photo")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Загрузить фото профиля")
    public ResponseEntity<?> uploadProfileImage(@Parameter(name = "Токен пользователя")
                                                @RequestHeader(HttpHeaders.AUTHORIZATION) String token,
                                                @Parameter(name = "Файл")
                                                @RequestParam(name = "file")
                                                MultipartFile file) {
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        
        if (file == null || file.isEmpty()) {
            return new ResponseEntity<>("File is empty", HttpStatus.BAD_REQUEST);
        }
        
        try {
            Person person = optionalPerson.get();
            boolean result = mediaSaver.saveProfilePhoto(file, person);
            return result ? new ResponseEntity<>("Ok", HttpStatus.OK) 
                        : new ResponseEntity<>("Failed to save file", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            // Логируем исключение
            e.printStackTrace();
            return new ResponseEntity<>("Internal Server Error: " + e.getMessage(), HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }
    @GetMapping("/profile")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Получить информацию о пользователе по токену")
    public ResponseEntity<?> getUserProfile(@RequestHeader(HttpHeaders.AUTHORIZATION) String token) {
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        
        PersonDTO personDTO = fromPerson(optionalPerson.get());
        String imageUrl = String.format("/uploads/profiles/%s.%s", optionalPerson.get().getUsername(), FilesFormat.IMAGE.getFormat());
        personDTO.setImageUrl(imageUrl);  
        return ResponseEntity.ok(personDTO);
    }
    @GetMapping("/check-user/{username}")
    @Operation(summary = "Проверить, зарегистрирован ли пользователь по имени пользователя")
    public ResponseEntity<?> checkIfUserExists(
            @Parameter(name = "Имя пользователя") 
            @PathVariable String username) {
        Optional<Person> optionalPerson = personService.findByUsername(username);
        if (optionalPerson.isPresent()) {
            PersonDTO personDTO = fromPerson(optionalPerson.get());
            String imageUrl = String.format("/uploads/profiles/%s.%s", optionalPerson.get().getUsername(), FilesFormat.IMAGE.getFormat());
            personDTO.setImageUrl(imageUrl);
            return ResponseEntity.ok(personDTO);
        }
        return new ResponseEntity<>("User not found", HttpStatus.NOT_FOUND);
    }
    @PatchMapping("/update")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Изменить информацию о пользователе")
    public ResponseEntity<?> changePersonInformation(
            @RequestBody PersonDTO personDTO,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String token) {
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        Person person = optionalPerson.get();
        
        if (personDTO.getDescription() != null) {
            person.setDescription(personDTO.getDescription());
        }
        
        // Обновляем linkName и linkUrl
        if (personDTO.getLinkName() != null) {
            person.setLinkName(personDTO.getLinkName());
        }
        
        if (personDTO.getLinkUrl() != null) {
            person.setLinkUrl(personDTO.getLinkUrl());
        }

        personService.save(person);
        return new ResponseEntity<>("Profile updated successfully", HttpStatus.OK);
    }

    @PostMapping("/update-description")
    @PreAuthorize("hasAnyAuthority('USER')")
    @Operation(summary = "Обновить описание профиля пользователя")
    public ResponseEntity<?> updateDescription(
            @Parameter(name = "Токен пользователя") @RequestHeader(HttpHeaders.AUTHORIZATION) String token,
            @Parameter(name = "Новое описание") @RequestBody String newDescription) {
        Optional<Person> optionalPerson = getPersonByToken(token);
        if (optionalPerson.isEmpty()) {
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
        Person person = optionalPerson.get();
        person.setDescription(newDescription);
        personService.save(person);
        return new ResponseEntity<>("Описание обновлено", HttpStatus.OK);
    }
    private void updateGuide(Guide guide, GuideDTO guideDTO) {
        if (guideDTO.getPrice() != 0) {
            guide.setPrice(guideDTO.getPrice());
        }
        if (guideDTO.getDescription() != null) {
            guide.setDescription(guideDTO.getDescription());
        }
    }

    private void updateChapter(Chapter chapter, ChapterDTO chapterDTO) {
        if (chapterDTO.getName() != null) {
            chapter.setName(chapterDTO.getName());
        }
        if (chapterDTO.getText() != null) {
            chapter.setText(chapterDTO.getText());
        }
    }

    

    private Optional<Person> getPersonByToken(String token) {
        String username = jwtTokenProvider.getUsername(token);
        Optional<Person> person = personService.findByUsername(username);
        person.ifPresent(p -> Hibernate.initialize(p.getReferralOwners()));
        return person;
    }
    

    private ChapterDTO fromChapter(Chapter chapter) { return modelMapper.map(chapter, ChapterDTO.class); }

    private GuideDTO fromGuide(Guide guide) {
        GuideDTO guideDTO = modelMapper.map(guide, GuideDTO.class);
    
        // Добавляем полный путь к основному изображению гайда
        if (guide.getMainImg() != null) {
            guideDTO.setMainImg(guide.getMainImg());
        }
    
        // Добавляем полный путь к изображениям и видео глав
        guideDTO.getChapters().forEach(chapter -> {
            if (chapter.getImg() != null) {
                chapter.setImg(chapter.getImg());
            }
            if (chapter.getVideo() != null) {
                chapter.setVideo(chapter.getVideo());
            }
        });
    
        // Проверяем, что weeklyEarnings не null
        if (guide.getWeeklyEarnings() == null) {
            guide.setWeeklyEarnings(0);  // Устанавливаем значение по умолчанию, если null
        }
    
        // Используем значение weeklyEarnings напрямую из объекта guide
        guideDTO.setWeeklyEarnings(guide.getWeeklyEarnings());
    
        return guideDTO;
    }
    
    

private PersonDTO fromPerson(Person person) {
    // Преобразуем основную информацию о пользователе
    PersonDTO personDTO = modelMapper.map(person, PersonDTO.class);

    // Инициализируем список рефералов вручную, используя referralOwners
    List<ReferralDTO> referralDTOs = person.getReferralOwners().stream()
        .map(referral -> {
            PersonDTO referralPersonDTO = modelMapper.map(referral.getReferral(), PersonDTO.class);
            return new ReferralDTO(referralPersonDTO);
        })
        .collect(Collectors.toList());

    // Устанавливаем список рефералов в personDTO
    personDTO.setReferrals(referralDTOs);

    return personDTO;
}



}

