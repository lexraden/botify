package com.example.guides.service;

import com.example.guides.model.Person;
import com.example.guides.repository.PersonRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;


@Service
public class RegistrationService {

    private final PersonRepository personRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${auth.password}")
    private String password;

    @Autowired
    public RegistrationService(PersonRepository personRepository, PasswordEncoder passwordEncoder) {
        this.personRepository = personRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public void register(Person person) {
        String referralLink = UUID.randomUUID().toString().replace("-", "");
        person.setReferralLink(referralLink);
        person.setPassword(passwordEncoder.encode(password));
        person.setRole("USER");
        personRepository.save(person);
    }
}
