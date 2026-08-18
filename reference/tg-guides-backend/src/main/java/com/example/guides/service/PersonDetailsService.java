package com.example.guides.service;

import com.example.guides.exception.UsernameNotFoundException;
import com.example.guides.model.Person;
import com.example.guides.repository.PersonRepository;
import com.example.guides.security.PersonDetails;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.stereotype.Service;

import java.util.Optional;

@Service
public class PersonDetailsService implements UserDetailsService {

    private final PersonRepository personRepository;

    @Autowired
    public PersonDetailsService(PersonRepository personRepository) {
        this.personRepository = personRepository;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        Optional<Person> optionalPerson = personRepository.findByUsername(username);
        if (optionalPerson.isEmpty()) {
            throw new UsernameNotFoundException(String.format("Username %s not found!", username));
        }
        return new PersonDetails(optionalPerson.get());
    }
}
