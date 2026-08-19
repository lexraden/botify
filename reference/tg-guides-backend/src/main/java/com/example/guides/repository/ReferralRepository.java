package com.example.guides.repository;

import com.example.guides.model.Person;
import com.example.guides.model.Referral;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ReferralRepository extends JpaRepository<Referral, Long> {
    boolean existsByReferralOwnerAndReferral(Person referralOwner, Person referral);
}
