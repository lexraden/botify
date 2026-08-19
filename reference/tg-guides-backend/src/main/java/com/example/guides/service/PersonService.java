package com.example.guides.service;

import com.example.guides.model.Person;
import com.example.guides.repository.PersonRepository;
import io.leangen.graphql.annotations.GraphQLArgument;
import io.leangen.graphql.annotations.GraphQLQuery;
import io.leangen.graphql.spqr.spring.annotations.GraphQLApi;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.Optional;

@Service
@GraphQLApi
public class PersonService {

    private final PersonRepository personRepository;

    @Autowired
    public PersonService(PersonRepository personRepository) {
        this.personRepository = personRepository;
    }

    @GraphQLQuery(name = "person")
    public Optional<Person> findByUsername(@GraphQLArgument(name = "username") String username) {
        return personRepository.findByUsername(username);
    }

    public Optional<Person> findById(long id) {
        return personRepository.findById(id);
    }
    public void updateBalance(Long personId, long amount) {
    Person person = findById(personId).orElseThrow(() -> new RuntimeException("Person not found"));
    person.setBalance(person.getBalance().add(BigDecimal.valueOf(amount))); 
    personRepository.save(person);
    }
    public Optional<Person> findByReferralLink(String referralLink) { return personRepository.findByReferralLink(referralLink); }

    @Transactional
    public void save(Person person) {
        personRepository.save(person);
    }
}
