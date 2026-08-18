package com.example.guides.controller;

import com.example.guides.dto.AuthDTO;
import com.example.guides.model.Person;
import com.example.guides.model.Referral;
import com.example.guides.security.JwtTokenProvider;
import com.example.guides.service.PersonService;
import com.example.guides.service.ReferralService;
import com.example.guides.service.RegistrationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.modelmapper.ModelMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

// Добавляем импорт для логирования
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/v1/auth")
@Tag(name = "Контроллер для авторизации")
@CrossOrigin(origins = "*")
public class AuthController {

    @Value("${auth.password}")
    private String password;

    private final PersonService personService;
    private final AuthenticationManager authenticationManager;
    private final ModelMapper modelMapper;
    private final JwtTokenProvider jwtTokenProvider;
    private final RegistrationService registrationService;
    private final ReferralService referralService;

    private static final Logger logger = LoggerFactory.getLogger(AuthController.class);

    @Autowired
    public AuthController(PersonService personService, AuthenticationManager authenticationManager, ModelMapper modelMapper, JwtTokenProvider jwtTokenProvider, RegistrationService registrationService, ReferralService referralService) {
        this.personService = personService;
        this.authenticationManager = authenticationManager;
        this.modelMapper = modelMapper;
        this.jwtTokenProvider = jwtTokenProvider;
        this.registrationService = registrationService;
        this.referralService = referralService;
    }

    @PostMapping("/init")
    @Operation(summary = "Аутентификация + регистрация пользователя")
    public ResponseEntity<?> initPerson(
            @Parameter(name = "Реферальная ссылка пользователя")
            @RequestParam(required = false) String ref,
            @Parameter(name = "Данные о пользователе, который совершает вход в приложение")
            @RequestBody AuthDTO authDTO) {

        logger.info("initPerson called with AuthDTO: {} and ref: {}", authDTO, ref);

        Optional<Person> optionalPerson = personService.findById(authDTO.getId());
        if (optionalPerson.isEmpty()) {
            logger.info("User with ID {} not found.", authDTO.getId());
            if (ref != null) {
                Optional<Person> byReferralLink = personService.findByReferralLink(ref);
                if (byReferralLink.isEmpty()) {
                    logger.warn("Invalid referral link: {}", ref);
                    return new ResponseEntity<>("Referral link is invalid", HttpStatus.BAD_REQUEST);
                } else {
                    logger.info("Registering new user with referral.");
                    return register(authDTO, byReferralLink.get());
                }
            } else {
                logger.info("Registering new user without referral.");
                return register(authDTO, null);
            }
        } else {
            logger.info("User with ID {} exists. Proceeding to login.", authDTO.getId());
            return login(authDTO);
        }
    }

    private ResponseEntity<?> login(AuthDTO authDTO) {
        String username = authDTO.getUsername();
        logger.info("Attempting to authenticate user: {}", username);
    
        try {
            authenticationManager.authenticate(new UsernamePasswordAuthenticationToken(username, password));
            logger.info("Authentication successful for user: {}", username);
        } catch (Exception e) {
            logger.error("Authentication failed for user: {}", username, e);
            return new ResponseEntity<>("Authentication failed", HttpStatus.UNAUTHORIZED);
        }
    
        Optional<Person> optionalPerson = personService.findById(authDTO.getId());
        if (optionalPerson.isPresent()) {
            Person person = optionalPerson.get();
            logger.info("User found: id={}, username={}", person.getId(), person.getUsername());
            String token = jwtTokenProvider.createToken(username, person.getRole());
            logger.info("Token generated for user: {}", username);
            return ResponseEntity.ok(createToken(token, username));
        } else {
            logger.error("User not found after authentication: ID {}", authDTO.getId());
            return new ResponseEntity<>("User not found", HttpStatus.BAD_REQUEST);
        }
    }
    

    private ResponseEntity<?> register(AuthDTO authDTO, Person referralOwner) {
        logger.info("Registering user with AuthDTO: {}", authDTO);
        Person person = toPerson(authDTO);

        try {
            registrationService.register(person);
            logger.info("User registered: {}", person);
        } catch (Exception e) {
            logger.error("Registration failed for user: {}", person, e);
            return new ResponseEntity<>("Registration failed", HttpStatus.INTERNAL_SERVER_ERROR);
        }

        if (referralOwner != null) {
            logger.info("Adding referral from owner: {} to new user: {}", referralOwner, person);
            try {
                referralService.save(new Referral(referralOwner, person));
                logger.info("Referral saved successfully.");
            } catch (Exception e) {
                logger.error("Failed to save referral for user: {}", person, e);
                // Решите, как обрабатывать эту ошибку: продолжить или вернуть ошибку
            }
        }

        String token = jwtTokenProvider.createToken(person.getUsername(), person.getRole());
        logger.info("Token generated for new user: {}", person.getUsername());
        return ResponseEntity.ok(createToken(token, person.getUsername()));
    }

    private Map<String, String> createToken(String token, String username) {
        logger.debug("Creating token for user: {}", username);
        Map<String, String> response = new HashMap<>();
        response.put("username", username);
        response.put("token", token);
        return response;
    }

    private Person toPerson(AuthDTO authDTO) {
        logger.debug("Converting AuthDTO to Person: {}", authDTO);
        Person person = modelMapper.map(authDTO, Person.class);
        logger.debug("Converted Person: {}", person);
        return person;
    }
}
