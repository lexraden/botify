package com.example.guides.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;
import javax.persistence.*;
import java.io.Serializable;


@Table(name = "referrals")
@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
@ToString(exclude = {"referralOwner", "referral"})
public class Referral implements Serializable {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    @ManyToOne
    @JoinColumn(name = "referral_owner_id")
    private Person referralOwner;

    @ManyToOne
    @JoinColumn(name = "referral_id")
    private Person referral;

    public Referral(Person referralOwner, Person referral) {
        this.referralOwner = referralOwner;
        this.referral = referral;
    }
}
